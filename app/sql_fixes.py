"""Small, dependency-free helpers applied to T5's SQL before validation.

1. fix_string_literals: Spider/SParC-style SQL writes string values with double quotes
   (WHERE dept_name = "Physics"). PostgreSQL reads "Physics" as an IDENTIFIER, so such
   queries fail validation. Convert them to single-quoted literals, but only where a
   value is expected (after a comparison operator, LIKE, BETWEEN, or inside IN (...))
   and never when the quoted text is a real table/column name.
2. choose_candidate: pick the best of several beam-search candidates
   (valid > needs_review > invalid, ties broken by beam rank).
"""
from __future__ import annotations

import re

_OPS = {"=", "!=", "<>", "<", ">", "<=", ">=", "like", "ilike", "between"}
_WORD = re.compile(r"[A-Za-z0-9_.$]+")
_OPCH = "=<>!"


def fix_string_literals(sql: str, known_names=frozenset()) -> str:
    known = {n.lower() for n in known_names}
    out, i, n = [], 0, len(sql)
    last = ""            # last significant token (lower-case word, operator, or punctuation)
    stack: list[bool] = []   # one entry per open "(": True when it directly follows IN
    between_and = 0      # pending 'AND' of a BETWEEN ... AND ... (value expected after it)
    while i < n:
        ch = sql[i]
        if ch.isspace():
            out.append(ch); i += 1; continue
        if ch == "'":                      # existing single-quoted literal: copy verbatim
            j = i + 1
            while j < n:
                if sql[j] == "'" and j + 1 < n and sql[j + 1] == "'": j += 2; continue
                if sql[j] == "'": break
                j += 1
            out.append(sql[i:j + 1]); i = j + 1; last = "lit"; continue
        if ch == '"':
            j = sql.find('"', i + 1)
            if j == -1:                    # unterminated: leave untouched
                out.append(sql[i:]); break
            content = sql[i + 1:j]
            value_slot = (last in _OPS or (last in ("(", ",") and stack and stack[-1])
                          or (last == "and" and between_and))
            if last == "and" and between_and: between_and -= 1
            if value_slot and content.lower() not in known:
                out.append("'" + content.replace("'", "''") + "'")
            else:
                out.append(sql[i:j + 1])
            i = j + 1; last = "lit"; continue
        if ch in _OPCH:
            j = i
            while j < n and sql[j] in _OPCH: j += 1
            out.append(sql[i:j]); last = sql[i:j]; i = j; continue
        m = _WORD.match(sql, i)
        if m:
            w = m.group(0); out.append(w); i = m.end(); last = w.lower()
            if last == "between": between_and += 1
            continue
        if ch == "(":
            stack.append(last == "in")
        elif ch == ")" and stack:
            stack.pop()
        out.append(ch); last = ch; i += 1
    return "".join(out)


def choose_candidate(candidates, validate):
    """-> (sql, validation, rank). `validate(sql)` returns a dict with a 'status' key."""
    best = None
    for rank, sql in enumerate(candidates):
        v = validate(sql)
        if v["status"] == "valid":
            return sql, v, rank
        if best is None or (v["status"] == "needs_review" and best[1]["status"] == "invalid"):
            best = (sql, v, rank)
    return best
