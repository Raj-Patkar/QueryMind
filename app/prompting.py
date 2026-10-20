"""Prompt builders that reproduce the formats the models were TRAINED on.

No torch / transformers imports here, so this module is cheap to unit-test.

T5 (Experiment 3, NL_Sparc_cosql.ipynb):
    translate conversational English to SQL: Question: <q> Schema: <schema> Conversation history: <h>
  schema  = "TABLE t: col(type) PRIMARY KEY, ... | TABLE u: ... | FOREIGN KEYS: t.a = u.b; ..."
            with Spider column types: text / number / time / boolean / others
  history = earlier USER QUESTIONS ONLY, joined with " | " (or "none")

Classifier (QueryMind_Ambiguity_Classifier.ipynb):
  schema  = "table(col, col); table(col, ...)"   (no types, no keys)
  history = plain earlier questions
"""
from __future__ import annotations

import re

MAX_HISTORY_TURNS = 6

_NUMBER = ("int", "numeric", "decimal", "real", "double", "float", "serial", "money")
_TEXT = ("char", "text", "citext", "uuid", "name")
_TIME = ("date", "time", "interval")


def spider_type(pg_type: str) -> str:
    """Map a PostgreSQL/SQLAlchemy type string to the Spider vocabulary."""
    t = (pg_type or "").lower()
    if "bool" in t:
        return "boolean"
    if any(k in t for k in _TIME):
        return "time"
    if any(k in t for k in _NUMBER):
        return "number"
    if any(k in t for k in _TEXT):
        return "text"
    return "others"


def build_t5_schema_text(schema_metadata: dict) -> str:
    tables = []
    fk_text = []
    for table in schema_metadata["tables"]:
        pk = set(table.get("primary_key") or [])
        cols = []
        for col in table["columns"]:
            pk_text = " PRIMARY KEY" if (col["name"] in pk or col.get("primary_key")) else ""
            cols.append(f'{col["name"]}({spider_type(col["type"])}){pk_text}')
        tables.append(f'TABLE {table["table"]}: ' + ", ".join(cols))

        for fk in table.get("foreign_keys") or []:
            for local, remote in zip(fk.get("columns") or [], fk.get("referred_columns") or []):
                fk_text.append(f'{table["table"]}.{local} = {fk["referred_table"]}.{remote}')

    text = " | ".join(tables)
    if fk_text:
        text += " | FOREIGN KEYS: " + "; ".join(fk_text)
    return text


def build_classifier_schema_text(schema_metadata: dict) -> str:
    return "; ".join(
        f'{t["table"]}(' + ", ".join(c["name"] for c in t["columns"]) + ")"
        for t in schema_metadata["tables"]
    )


def normalize_history(history: str | None, max_turns: int = MAX_HISTORY_TURNS) -> list[str]:
    """Return earlier user questions only, oldest first.

    Accepts the plain "none", a " | "-joined string, or the legacy
    "user: ...\\nassistant: ..." transcript (assistant lines are dropped because
    the models never saw assistant text during training).
    """
    if not history or history.strip().lower() == "none":
        return []
    lines = [ln.strip() for ln in re.split(r"\n+", history) if ln.strip()]
    questions: list[str] = []
    for ln in lines:
        low = ln.lower()
        if low.startswith("assistant:"):
            continue
        if low.startswith("user:"):
            ln = ln[5:].strip()
        questions.extend(q.strip() for q in ln.split(" | ") if q.strip())
    return questions[-max_turns:]


def history_for_t5(questions: list[str]) -> str:
    return " | ".join(questions) if questions else "none"


def history_for_classifier(questions: list[str]) -> str:
    return " | ".join(questions) if questions else "none"


def build_t5_prompt(question: str, t5_schema: str, history_text: str) -> str:
    return (
        "translate conversational English to SQL: "
        "Question: " + question.strip()
        + " Schema: " + t5_schema
        + " Conversation history: " + (history_text or "none")
    )
