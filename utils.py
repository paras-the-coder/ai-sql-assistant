"""
utils.py  —  Helper utilities for the Text-to-SQL project.
"""

import sqlite3
import os
import re
from tabulate import tabulate
from typing import Optional


def get_db_schema(db_path: str) -> str:
    """Extract CREATE TABLE statements from the SQLite DB to use as schema context."""
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name")
        rows = cur.fetchall()
    return "\n\n".join(f"-- Table: {name}\n{sql};" for name, sql in rows if sql)


def execute_query(db_path: str, sql: str) -> tuple[list, list]:
    """
    Execute a SQL query and return (rows, column_names).
    Opens DB in read-only mode to prevent any writes.
    Raises sqlite3.Error on bad SQL.
    """
    uri_path = f"file:{os.path.abspath(db_path).replace('\\', '/')}?mode=ro"
    with sqlite3.connect(uri_path, uri=True) as conn:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description] if cur.description else []
    return rows, cols


def format_results(rows: list, cols: list, max_rows: int = 20) -> str:
    """Pretty-print query results as a table string."""
    if not rows:
        return "(No results)"
    display_rows = rows[:max_rows]
    table = tabulate(display_rows, headers=cols, tablefmt="rounded_outline", floatfmt=".2f")
    if len(rows) > max_rows:
        table += f"\n  ... and {len(rows) - max_rows} more rows"
    return table


def extract_sql(raw: str) -> str:
    """
    Extract clean SQL from an LLM response that might include
    markdown fences, explanations, etc. Only captures SELECT / WITH.
    """
    # Remove markdown code blocks
    raw = re.sub(r"```sql\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"```", "", raw)
    # Grab the first SELECT / WITH statement
    match = re.search(
        r"((?:WITH|SELECT)\b.+)",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return match.group(1).strip() if match else raw.strip()


def validate_sql(sql: str) -> tuple[bool, str]:
    """Strict read-only guardrail using word-boundary regex."""
    clean_sql = sql.strip()
    if not re.match(r"^(SELECT|WITH)\b", clean_sql, re.IGNORECASE):
        return False, "Blocked: Only SELECT / READ queries are permitted."

    forbidden = r"\b(UPDATE|DELETE|DROP|INSERT|ALTER|CREATE|TRUNCATE|ATTACH|DETACH)\b"
    match = re.search(forbidden, clean_sql, re.IGNORECASE)
    if match:
        return False, f"Blocked: Operation '{match.group(0).upper()}' is strictly prohibited."

    return True, ""


def results_to_string(rows: list, cols: list, max_rows: int = 10) -> str:
    """Compact string representation for LLM context (avoid huge token cost)."""
    if not rows:
        return "No results found."
    lines = [", ".join(cols)]
    for row in rows[:max_rows]:
        lines.append(", ".join(str(v) for v in row))
    if len(rows) > max_rows:
        lines.append(f"... ({len(rows) - max_rows} more rows)")
    return "\n".join(lines)


def check_db_exists(db_path: str) -> bool:
    """Check the database has been seeded."""
    if not os.path.exists(db_path):
        return False
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cur.fetchall()
    return len(tables) >= 3
