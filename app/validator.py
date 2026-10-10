import sqlglot
from sqlglot import exp
from app.schema import SCHEMA_COLUMNS

def validate_sql_schema_aware(sql, schema=SCHEMA_COLUMNS, dialect="postgres"):
    """Conservative static validation only. Never executes SQL."""
    result = {"status": None, "issues": [], "warnings": [], "normalized_sql": None,
              "tables": [], "columns": []}
    if not isinstance(sql, str) or not sql.strip():
        result["status"] = "invalid"
        result["issues"].append("SQL is empty.")
        return result
    try:
        statements = [s for s in sqlglot.parse(sql, read=dialect) if s is not None]
    except Exception as exc:
        result["status"] = "invalid"
        result["issues"].append(f"SQL parse error: {exc}")
        return result
    if len(statements) != 1:
        result["status"] = "invalid"
        result["issues"].append(f"Expected exactly one SQL statement; found {len(statements)}.")
        return result
    tree = statements[0]
    result["normalized_sql"] = tree.sql(dialect=dialect)
    if not isinstance(tree, exp.Select):
        if isinstance(tree, exp.Query) and tree.find(exp.Select) is not None:
            result["status"] = "needs_review"
            result["warnings"].append("CTE or advanced query structure requires scope-aware validation.")
        else:
            result["status"] = "invalid"
            result["issues"].append("Only read-only SELECT queries are allowed.")
        return result
    if tree.find(exp.With) is not None or tree.find(exp.Subquery) is not None or tree.find(exp.Union) is not None:
        result["status"] = "needs_review"
        result["warnings"].append("CTEs, subqueries, and set operations require scope-aware validation.")
        return result
    table_nodes = list(tree.find_all(exp.Table))
    if tree.args.get("joins") or len(table_nodes) > 1:
        result["status"] = "needs_review"
        result["warnings"].append("Multiple tables/joins need scope-aware column resolution.")
        return result
    alias_map, table_names = {}, []
    for node in table_nodes:
        name = node.name.lower()
        if node.db or node.catalog:
            result["status"] = "needs_review"
            result["warnings"].append("Schema-qualified table names are outside the supported subset.")
            return result
        if name not in schema:
            result["issues"].append(f"Unknown table: '{node.name}'.")
            continue
        table_names.append(name)
        alias_map[(node.alias or name).lower()] = name
    result["tables"] = table_names
    if table_nodes and len(table_names) != len(table_nodes):
        result["status"] = "invalid"
        return result
    projection_aliases = {p.alias.lower() for p in tree.expressions if isinstance(p, exp.Alias) and p.alias}
    seen_columns = []
    for col in tree.find_all(exp.Column):
        col_name = col.name.lower()
        if col_name == "*":
            continue
        qualifier = (col.table or "").lower()
        if qualifier:
            if qualifier not in alias_map:
                result["issues"].append(f"Unknown table/alias qualifier '{col.table}' on column '{col.name}'.")
                continue
            target = alias_map[qualifier]
            if col_name not in {c.lower() for c in schema[target]}:
                result["issues"].append(f"Unknown column '{col.name}' on table '{target}'.")
                continue
        else:
            if col_name in projection_aliases:
                continue
            if not table_names:
                result["warnings"].append(f"Could not schema-check column '{col.name}' because there is no FROM clause.")
                continue
            matches = [t for t in table_names if col_name in {c.lower() for c in schema[t]}]
            if not matches:
                result["issues"].append(f"Unknown column '{col.name}' for table(s): {', '.join(table_names)}.")
                continue
            if len(matches) > 1:
                result["issues"].append(f"Ambiguous unqualified column '{col.name}'; qualify it with a table name/alias.")
                continue
        seen_columns.append(col.sql(dialect=dialect))
    result["columns"] = sorted(set(seen_columns))
    has_aggregate = any(isinstance(n, exp.AggFunc) for projection in tree.expressions for n in projection.walk())
    group_clause = tree.args.get("group")
    if has_aggregate:
        non_aggregate = []
        for projection in tree.expressions:
            core = projection.this if isinstance(projection, exp.Alias) else projection
            contains_agg = any(isinstance(n, exp.AggFunc) for n in core.walk())
            has_col = any(isinstance(n, exp.Column) for n in core.walk())
            if not contains_agg and has_col:
                non_aggregate.append(core.sql(dialect=dialect))
        if non_aggregate and not group_clause:
            result["issues"].append("Aggregate and non-aggregate expressions are selected together without GROUP BY: " + ", ".join(non_aggregate) + ".")
        elif non_aggregate and group_clause:
            group_sql = {g.sql(dialect=dialect).lower() for g in group_clause.expressions}
            missing = [x for x in non_aggregate if x.lower() not in group_sql]
            if missing:
                result["issues"].append("Selected non-aggregate expression(s) are not listed in GROUP BY: " + ", ".join(missing) + ".")
    if result["issues"]:
        result["status"] = "invalid"
    else:
        result["status"] = "valid"
        result["warnings"].append("Static checks passed only; semantic correctness is not guaranteed.")
    return result
