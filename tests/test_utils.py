"""
tests/test_utils.py  —  Unit & security tests for Text-to-SQL validators and database execution.
Run:  pytest
"""

import sqlite3
import pytest
from utils import validate_sql, extract_sql, execute_query, compare_result_sets


def test_validate_sql_valid_queries():
    """Verify standard read-only SELECT and WITH queries pass."""
    ok, _ = validate_sql("SELECT name, salary FROM employees WHERE is_active = 1;")
    assert ok is True

    ok, _ = validate_sql("WITH dept_summary AS (SELECT dept_id FROM departments) SELECT * FROM dept_summary;")
    assert ok is True


def test_validate_sql_blocks_destructive_commands():
    """Verify write, drop, and schema modification commands are blocked."""
    destructive = [
        "DROP TABLE employees;",
        "DELETE FROM departments;",
        "UPDATE employees SET salary = 999999;",
        "INSERT INTO departments VALUES (10, 'Hacked', 'Nowhere', 0, 'Evil');",
        "ALTER TABLE employees ADD COLUMN ssn TEXT;",
        "CREATE TABLE backdoor (id INT);",
        "TRUNCATE TABLE sales;",
    ]
    for sql in destructive:
        ok, reason = validate_sql(sql)
        assert ok is False
        assert "Blocked" in reason


def test_validate_sql_blocks_obfuscated_bypasses():
    """Verify whitespace variants (tabs, newlines, semicolons) cannot bypass the guardrail."""
    bypasses = [
        "SELECT 1; DROP\tTABLE employees;",
        "SELECT 1;\nDELETE\nFROM employees;",
        "SELECT 1; ATTACH DATABASE 'evil.db' AS evil;",
        "SELECT 1; DETACH DATABASE evil;",
    ]
    for sql in bypasses:
        ok, reason = validate_sql(sql)
        assert ok is False
        assert "Blocked" in reason


def test_extract_sql_strips_markdown_and_prose():
    """Verify markdown fences and trailing comments/assumptions are stripped."""
    raw_markdown = "```sql\nSELECT name FROM employees;\n```"
    assert extract_sql(raw_markdown) == "SELECT name FROM employees;"

    raw_with_prose = "```sql\nSELECT count(*) FROM departments;\n```\nNote: I assumed all active departments."
    assert extract_sql(raw_with_prose) == "SELECT count(*) FROM departments;"


def test_execute_query_readonly_enforced():
    """Verify read-only SQLite URI prevents any physical writes even if validation is skipped."""
    with pytest.raises(sqlite3.OperationalError, match="readonly database"):
        execute_query("db/company.db", "UPDATE employees SET salary = 0;")


def test_execute_query_max_rows_cap():
    """Verify query execution respects the max_rows ceiling."""
    rows, _ = execute_query("db/company.db", "SELECT * FROM sales;", max_rows=5)
    assert len(rows) <= 5


def test_validate_sql_ignores_keywords_inside_string_literals():
    """A forbidden word inside a quoted value is data, not a command."""
    ok, _ = validate_sql("SELECT name FROM employees WHERE role = 'Delete Specialist';")
    assert ok is True
    ok, _ = validate_sql("SELECT 'a'; DROP TABLE employees; SELECT 'b';")
    assert ok is False


def test_extract_sql_keeps_semicolon_inside_string_literal():
    assert extract_sql("SELECT name FROM employees WHERE name = 'a;b'; -- note") == \
        "SELECT name FROM employees WHERE name = 'a;b';"


def test_execute_query_timeout_aborts_runaway_query():
    runaway = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT count(*) FROM c;"
    with pytest.raises(sqlite3.OperationalError, match="interrupted"):
        execute_query("db/company.db", runaway, timeout_seconds=0.5)


def test_compare_result_sets_exact_and_order_insensitive():
    assert compare_result_sets([("a", 1), ("b", 2)], [("b", 2), ("a", 1)])
    assert not compare_result_sets([("a", 1), ("b", 2)], [("a", 1), ("b", 3)])


def test_compare_result_sets_allows_extra_or_reordered_columns():
    assert compare_result_sets([("Eng", 5)], [(5, "Eng")])
    assert compare_result_sets([("Eng",), ("Ops",)], [("Eng", 5), ("Ops", 3)])


def test_compare_result_sets_numeric_scalar_must_match_exactly():
    """A COUNT of 1 must not be satisfied by an unrelated row that happens to contain a 1."""
    assert compare_result_sets([(1,)], [(1,)])
    assert not compare_result_sets([(1,)], [("Priya", 1, "x")])


def test_compare_result_sets_text_scalar_may_have_extra_columns():
    assert compare_result_sets([("Bangalore",)], [("Engineering", "Bangalore")])


def test_compare_result_sets_tolerates_wide_results():
    gold = [("P1", 900), ("P2", 800)]
    wide = [("P1", 900, "a", "b", "c", "d", "e"), ("P2", 800, "a", "b", "c", "d", "e")]
    assert compare_result_sets(gold, wide)


def test_compare_result_sets_empty_gold_never_passes():
    assert not compare_result_sets([], [])