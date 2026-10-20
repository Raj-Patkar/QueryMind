from app.sql_fixes import choose_candidate, fix_string_literals

KNOWN = {"instructor", "student", "name", "dept_name", "salary", "title", "id"}
f = lambda s: fix_string_literals(s, KNOWN)


def test_equals_and_like():
    assert f('SELECT name FROM instructor WHERE dept_name = "Physics"') == "SELECT name FROM instructor WHERE dept_name = 'Physics'"
    assert f('SELECT * FROM student WHERE name LIKE "S%"') == "SELECT * FROM student WHERE name LIKE 'S%'"
    assert f('WHERE dept_name != "Biology" AND salary > 5') == "WHERE dept_name != 'Biology' AND salary > 5"


def test_in_list_and_between():
    assert f('WHERE semester IN ("Fall", "Spring")') == "WHERE semester IN ('Fall', 'Spring')"
    assert f('WHERE x BETWEEN "a" AND "b"') == "WHERE x BETWEEN 'a' AND 'b'"


def test_identifiers_are_left_alone():
    assert f('SELECT "name" FROM instructor') == 'SELECT "name" FROM instructor'
    assert f('SELECT name FROM "instructor" WHERE "dept_name" = "dept_name"') == 'SELECT name FROM "instructor" WHERE "dept_name" = "dept_name"'
    # a quoted name in a select list / non-value position is not turned into a literal
    assert f('SELECT "Physics" FROM instructor') == 'SELECT "Physics" FROM instructor'


def test_single_quotes_and_escapes():
    assert f("WHERE a = 'x \"y\"'") == "WHERE a = 'x \"y\"'"
    assert f('WHERE a = "O\'Brien"') == "WHERE a = 'O''Brien'"
    assert f('WHERE a = "unterminated') == 'WHERE a = "unterminated'


def test_subquery_and_in_subquery_paren():
    assert f('WHERE dept_name IN (SELECT dept_name FROM department WHERE building = "Taylor")') == \
        "WHERE dept_name IN (SELECT dept_name FROM department WHERE building = 'Taylor')"


def test_choose_candidate_prefers_valid_then_review():
    status = {"a": "invalid", "b": "needs_review", "c": "valid", "d": "valid"}
    v = lambda s: {"status": status[s]}
    assert choose_candidate(["a", "b", "c", "d"], v)[::2] == ("c", 2)
    assert choose_candidate(["a", "b"], v)[::2] == ("b", 1)
    assert choose_candidate(["a"], v)[::2] == ("a", 0)
