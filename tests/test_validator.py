from app.validator import validate_sql_schema_aware

def test_simple_select_valid():
    assert validate_sql_schema_aware("SELECT name FROM student")["status"] == "valid"

def test_delete_rejected():
    result = validate_sql_schema_aware("DELETE FROM student")
    assert result["status"] == "invalid"

def test_unknown_column_rejected():
    result = validate_sql_schema_aware("SELECT department FROM student")
    assert result["status"] == "invalid"

def test_aggregate_missing_group_by_rejected():
    result = validate_sql_schema_aware("SELECT dept_name, COUNT(*) FROM student")
    assert result["status"] == "invalid"

def test_cte_goes_to_review():
    result = validate_sql_schema_aware("WITH s AS (SELECT name FROM student) SELECT name FROM s")
    assert result["status"] == "needs_review"
