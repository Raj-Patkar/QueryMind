"""Per-request PostgreSQL connection helpers for QueryMind.

Requires: SQLAlchemy 2.x and psycopg 3.
This module discovers schema and executes read-only SELECT queries only.
Do not expose arbitrary connection strings on a public server without authentication
and outbound-network restrictions.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.exc import SQLAlchemyError
import sqlglot
from sqlglot import exp


DEFAULT_SCHEMA = "public"
MAX_ROWS = 200
CONNECT_TIMEOUT_SECONDS = 8
STATEMENT_TIMEOUT_MS = 5000


class DatabaseConnectionError(RuntimeError):
    """Raised when a PostgreSQL connection cannot be established."""


class UnsafeQueryError(ValueError):
    """Raised when SQL is not a single read-only SELECT query."""


def _validate_postgres_url(connection_string: str) -> URL:
    if not isinstance(connection_string, str) or not connection_string.strip():
        raise ValueError("A PostgreSQL connection string is required.")

    raw = connection_string.strip()
    parsed = urlparse(raw)
    if parsed.scheme not in {"postgresql", "postgresql+psycopg"}:
        raise ValueError(
            "Only PostgreSQL URLs are supported, for example "
            "postgresql://user:password@host:5432/database."
        )
    if not parsed.hostname or not parsed.path or parsed.path == "/":
        raise ValueError("The connection string must include a host and database name.")

    try:
        url = make_url(raw)
    except Exception as exc:
        raise ValueError("The PostgreSQL connection string is malformed.") from exc

    # Normalize to psycopg 3; URL credentials remain handled by SQLAlchemy.
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return url


def create_postgres_engine(connection_string: str) -> Engine:
    """Create and verify an engine for a PostgreSQL connection string."""
    url = _validate_postgres_url(connection_string)
    try:
        engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=1,
            max_overflow=0,
            pool_timeout=CONNECT_TIMEOUT_SECONDS,
            connect_args={
                "connect_timeout": CONNECT_TIMEOUT_SECONDS,
                "options": f"-c statement_timeout={STATEMENT_TIMEOUT_MS}",
                "application_name": "QueryMind",
            },
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as exc:
        try:
            engine.dispose()  # type: ignore[possibly-undefined]
        except Exception:
            pass
        raise DatabaseConnectionError(
            "Could not connect to PostgreSQL. Check the host, credentials, database, "
            "TLS settings, and network access."
        ) from exc


def discover_schema(engine: Engine, schemas: list[str] | None = None) -> dict[str, Any]:
    """Return table/column/key metadata and a compact schema string for model prompts.

    Defaults to the `public` schema. Pass an explicit allowlist of schema names
    if the database uses another schema. System schemas are intentionally excluded.
    """
    schema_names = schemas or [DEFAULT_SCHEMA]
    inspector = inspect(engine)
    tables: list[dict[str, Any]] = []
    prompt_lines: list[str] = []

    for schema_name in schema_names:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", schema_name):
            raise ValueError(f"Invalid schema name: {schema_name!r}")

        for table_name in inspector.get_table_names(schema=schema_name):
            columns = inspector.get_columns(table_name, schema=schema_name)
            pk = inspector.get_pk_constraint(table_name, schema=schema_name) or {}
            fks = inspector.get_foreign_keys(table_name, schema=schema_name) or []

            column_items = [
                {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": bool(col.get("nullable", True)),
                    "primary_key": col["name"] in (pk.get("constrained_columns") or []),
                }
                for col in columns
            ]
            fk_items = [
                {
                    "columns": fk.get("constrained_columns") or [],
                    "referred_schema": fk.get("referred_schema") or schema_name,
                    "referred_table": fk.get("referred_table"),
                    "referred_columns": fk.get("referred_columns") or [],
                }
                for fk in fks
            ]

            qualified = table_name
            tables.append({
                "schema": schema_name,
                "table": table_name,
                "columns": column_items,
                "primary_key": pk.get("constrained_columns") or [],
                "foreign_keys": fk_items,
            })
            cols_for_prompt = ", ".join(
                f'{col["name"]} ({col["type"]})' for col in column_items
            )
            prompt_lines.append(f"{qualified}({cols_for_prompt})")

    if not tables:
        raise DatabaseConnectionError(
            "Connected successfully, but no tables were found in the selected schema(s)."
        )

    return {
        "tables": tables,
        "schema_text": "\n".join(prompt_lines),
        "table_count": len(tables),
    }


def validate_read_only_select(sql: str) -> str:
    """Allow exactly one SELECT statement (including WITH ... SELECT).

    SQLGlot parses the query; database-side read-only transactions are an additional
    protection. This is not a substitute for least-privilege DB credentials.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise UnsafeQueryError("SQL is empty.")

    try:
        statements = sqlglot.parse(sql, read="postgres")
    except Exception as exc:
        raise UnsafeQueryError("SQL could not be parsed as PostgreSQL.") from exc

    statements = [stmt for stmt in statements if stmt is not None]
    if len(statements) != 1:
        raise UnsafeQueryError("Only one SQL statement is allowed.")

    parsed = statements[0]
    # A WITH query is represented as Select with CTEs in SQLGlot.
    if not isinstance(parsed, exp.Select):
        raise UnsafeQueryError("Only SELECT queries are allowed.")

    forbidden = (
        exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter,
        exp.Command, exp.Merge, exp.Transaction, exp.Copy, exp.Pragma,
    )
    if any(parsed.find(kind) is not None for kind in forbidden):
        raise UnsafeQueryError("The query contains a disallowed operation.")

    return parsed.sql(dialect="postgres")


def execute_read_only(
    engine: Engine,
    sql: str,
    max_rows: int = MAX_ROWS,
    timeout_ms: int = STATEMENT_TIMEOUT_MS,
) -> dict[str, Any]:
    """Execute a validated read-only SELECT and return bounded JSON-friendly rows."""
    if max_rows < 1 or max_rows > MAX_ROWS:
        raise ValueError(f"max_rows must be between 1 and {MAX_ROWS}.")
    normalized_sql = validate_read_only_select(sql)

    try:
        with engine.connect() as conn:
            # PostgreSQL enforces read-only mode for this transaction.
            with conn.begin():
                conn.execute(text("SET TRANSACTION READ ONLY"))
                conn.execute(
                    text("SELECT set_config('statement_timeout', :timeout, true)"),
                    {"timeout": f"{int(timeout_ms)}ms"},
                )
                result = conn.execute(text(normalized_sql))
                columns = list(result.keys())
                rows = result.fetchmany(max_rows + 1)
                truncated = len(rows) > max_rows
                rows = rows[:max_rows]

                def json_value(value: Any) -> Any:
                    if value is None or isinstance(value, (str, int, float, bool)):
                        return value
                    if hasattr(value, "isoformat"):
                        return value.isoformat()
                    return str(value)

                return {
                    "status": "executed",
                    "sql": normalized_sql,
                    "columns": columns,
                    "rows": [
                        {key: json_value(value) for key, value in zip(columns, row)}
                        for row in rows
                    ],
                    "row_count": len(rows),
                    "truncated": truncated,
                }
    except (UnsafeQueryError, ValueError):
        raise
    except SQLAlchemyError as exc:
        raise DatabaseConnectionError(
            "The query could not be executed against the configured database."
        ) from exc
