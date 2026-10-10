"""Static validation of generated SQL against dynamically discovered PostgreSQL schema."""
from __future__ import annotations

import sqlglot
from sqlglot import exp

from app.postgres_connector import UnsafeQueryError, validate_read_only_select


def validate_sql_against_schema(sql: str, schema_metadata: dict) -> dict:
    issues = []
    warnings = []
    try:
        normalized = validate_read_only_select(sql)
        parsed = sqlglot.parse_one(normalized, read="postgres")
    except UnsafeQueryError as exc:
        return {
            "status": "invalid",
            "issues": [str(exc)],
            "warnings": [],
            "normalized_sql": sql,
            "tables": [],
            "columns": [],
        }
    except Exception:
        return {
            "status": "invalid",
            "issues": ["SQL could not be parsed as a supported PostgreSQL SELECT."],
            "warnings": [],
            "normalized_sql": sql,
            "tables": [],
            "columns": [],
        }

    all_tables = schema_metadata.get("tables", [])
    table_map = {
        (item["schema"].lower(), item["table"].lower()): item
        for item in all_tables
    }
    table_map_by_name = {}
    for item in all_tables:
        table_map_by_name.setdefault(item["table"].lower(), []).append(item)

    query_tables = list(parsed.find_all(exp.Table))
    used_tables = []
    alias_map = {}
    referenced_table_items = []

    cte_names = {
        cte.alias_or_name.lower()
        for cte in parsed.find_all(exp.CTE)
        if cte.alias_or_name
    }

    for table in query_tables:
        table_name = (table.name or "").lower()
        if table_name in cte_names:
            continue
        schema_name = (table.db or "public").lower()
        key = (schema_name, table_name)

        item = table_map.get(key)
        if item is None and not table.db:
            candidates = table_map_by_name.get(table_name, [])
            if len(candidates) == 1:
                item = candidates[0]
            elif len(candidates) > 1:
                issues.append(
                    f"Table '{table_name}' exists in multiple schemas; qualify it with its schema."
                )
            else:
                issues.append(f"Unknown table '{table_name}' in the connected schema.")
        elif item is None:
            issues.append(
                f"Unknown table '{schema_name}.{table_name}' in the connected schema."
            )

        if item is not None:
            used_tables.append(f'{item["schema"]}.{item["table"]}')
            referenced_table_items.append(item)
            alias = table.alias_or_name.lower()
            alias_map[alias] = item
            alias_map[table.name.lower()] = item

    columns_found = []
    seen_columns = set()

    for column in parsed.find_all(exp.Column):
        col_name = (column.name or "").lower()
        if not col_name or col_name == "*":
            continue
        if column.table:
            qualifier = column.table.lower()
            item = alias_map.get(qualifier)
            if item is None:
                # The qualifier may be a schema/table name; do not silently accept it.
                issues.append(
                    f"Unknown table/alias qualifier '{column.table}' on column '{column.name}'."
                )
                continue
            known_cols = {c["name"].lower() for c in item["columns"]}
            if col_name not in known_cols:
                issues.append(
                    f"Unknown column '{column.name}' for table '{item['table']}'."
                )
        else:
            matches = [
                item for item in referenced_table_items
                if col_name in {c["name"].lower() for c in item["columns"]}
            ]
            if not matches:
                issues.append(
                    f"Unknown column '{column.name}' for the tables referenced by this query."
                )
            elif len(matches) > 1:
                warnings.append(
                    f"Unqualified column '{column.name}' exists in multiple referenced tables; verify intended meaning."
                )

        if col_name not in seen_columns:
            columns_found.append(column.name)
            seen_columns.add(col_name)

    if issues:
        status = "invalid"
    else:
        status = "valid"
        if warnings:
            status = "needs_review"

    return {
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "normalized_sql": normalized,
        "tables": sorted(set(used_tables)),
        "columns": columns_found,
    }
