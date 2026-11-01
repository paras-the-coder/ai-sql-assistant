"""
utils.py  —  Helper utilities for the Text-to-SQL project.
"""

import sqlite3
import os
import re
import time
from collections import Counter
from itertools import combinations, permutations
from tabulate import tabulate


def get_db_schema(db_path: str) -> str:
    """Extract CREATE TABLE statements from the SQLite DB to use as schema context."""
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name")
        rows = cur.fetchall()
    return "\n\n".join(f"-- Table: {name}\n{sql};" for name, sql in rows if sql)


def execute_query(db_path: str, sql: str, timeout_seconds: float = 5.0, max_rows: int = 100) -> tuple[list, list]:
    """
    Execute a SQL query and return (rows, column_names).
    Opens DB in read-only mode to prevent any writes.
    Enforces a query timeout and max row cap to prevent runaway queries.
    Raises sqlite3.Error on bad SQL.
    """
    start_time = time.time()

    def timeout_handler():
        if time.time() - start_time > timeout_seconds:
            return 1  # non-zero aborts the query
        return 0

    uri_path = f"file:{os.path.abspath(db_path).replace('\\', '/')}?mode=ro"
    with sqlite3.connect(uri_path, uri=True) as conn:
        conn.set_progress_handler(timeout_handler, 1000)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchmany(max_rows)
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
    if not match:
        return raw.strip()
    sql = match.group(1).strip()
    # Keep only the first complete statement (complete_statement ignores ';' inside string literals)
    for i, ch in enumerate(sql):
        if ch == ";" and sqlite3.complete_statement(sql[: i + 1]):
            return sql[: i + 1]
    return sql


def validate_sql(sql: str) -> tuple[bool, str]:
    """Strict read-only guardrail using word-boundary regex."""
    clean_sql = sql.strip()
    if not re.match(r"^(SELECT|WITH)\b", clean_sql, re.IGNORECASE):
        return False, "Blocked: Only SELECT / READ queries are permitted."

    forbidden = r"\b(UPDATE|DELETE|DROP|INSERT|ALTER|CREATE|TRUNCATE|ATTACH|DETACH)\b"
    # Ignore text inside '...' literals so values like 'Delete Specialist' aren't flagged
    unquoted_sql = re.sub(r"'(?:[^']|'')*'", "''", clean_sql)
    match = re.search(forbidden, unquoted_sql, re.IGNORECASE)
    if match:
        return False, f"Blocked: Operation '{match.group(0).upper()}' is strictly prohibited."

    return True, ""


def normalize_row_counter(rows: list[tuple]) -> Counter:
    """Order-insensitive multiset of rows with normalised cell text, for fair comparison."""
    normalized = []
    for row in rows:
        cells = []
        for val in row:
            if isinstance(val, float):
                cells.append(str(round(val, 2)))
            elif val is None:
                cells.append("")
            else:
                cells.append(str(val).strip().lower())
        normalized.append(tuple(cells))
    return Counter(normalized)


def compare_result_sets(gold_rows: list[tuple], gen_rows: list[tuple]) -> bool:
    """
    Execution-accuracy check. True if the generated rows equal the gold rows as a
    multiset, or if the gold columns appear (in any order) among the generated
    columns. A single *numeric* gold answer (e.g. a COUNT) must match exactly, so an
    unrelated row that merely contains the same number can never pass.
    """
    if not gold_rows or len(gold_rows) != len(gen_rows):
        return False

    gold = normalize_row_counter(gold_rows)
    if gold == normalize_row_counter(gen_rows):
        return True

    n_gold, n_gen = len(gold_rows[0]), len(gen_rows[0])
    scalar_number = len(gold_rows) == 1 and n_gold == 1 and isinstance(gold_rows[0][0], (int, float))
    if scalar_number or n_gen < n_gold or n_gen > 12:  # 12 bounds the column-combination search
        return False

    for cols in combinations(range(n_gen), n_gold):
        for perm in permutations(cols):
            candidate = [tuple(row[i] for i in perm) for row in gen_rows]
            if normalize_row_counter(candidate) == gold:
                return True
    return False


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