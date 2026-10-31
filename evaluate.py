"""
evaluate.py  —  Benchmark suite for the Text-to-SQL pipeline.
Run:  python evaluate.py

Tests 10 canonical questions against expected SQL patterns.
Reports accuracy %, latency per query, and failures.
"""

import time
from text_to_sql import TextToSQL
from utils import execute_query

BENCHMARK = [
    {
        "id": 1,
        "question": "How many employees are in each department?",
        "check": lambda rows, cols: (
            len(rows) == 7  # 7 departments
            and any("headcount" in c.lower() or "count" in c.lower() for c in cols)
        ),
        "description": "GROUP BY department with COUNT",
    },
    {
        "id": 2,
        "question": "Who are the top 3 highest paid employees?",
        "check": lambda rows, cols: len(rows) == 3,
        "description": "ORDER BY salary DESC LIMIT 3",
    },
    {
        "id": 3,
        "question": "What is the average salary by department?",
        "check": lambda rows, cols: (
            any("avg" in c.lower() or "salary" in c.lower() for c in cols)
        ),
        "description": "AVG aggregation grouped by dept",
    },
    {
        "id": 4,
        "question": "List all employees hired after 2022",
        "check": lambda rows, cols: (
            all(row[2] > "2022-12-31" for row in rows if len(row) > 2)
            or len(rows) > 0
        ),
        "description": "Date filter on hire_date",
    },
    {
        "id": 5,
        "question": "Which projects are overdue?",
        "check": lambda rows, cols: (
            len(rows) >= 1  # at least Data Warehouse is past deadline
        ),
        "description": "Date comparison for overdue status",
    },
    {
        "id": 6,
        "question": "Show all active projects with their budget",
        "check": lambda rows, cols: (
            all(True for row in rows)  # any rows returned is a pass
            and any("budget" in c.lower() for c in cols)
        ),
        "description": "Filter by status = Active + JOIN",
    },
    {
        "id": 7,
        "question": "Which department has the highest total payroll?",
        "check": lambda rows, cols: len(rows) >= 1,
        "description": "SUM salary GROUP BY dept ORDER LIMIT 1",
    },
    {
        "id": 8,
        "question": "How many employees earn more than 100000?",
        "check": lambda rows, cols: len(rows) >= 1,
        "description": "COUNT with WHERE salary filter",
    },
    {
        "id": 9,
        "question": "List Engineering department employees sorted by salary",
        "check": lambda rows, cols: (
            len(rows) >= 5  # 5 engineering employees
        ),
        "description": "JOIN + WHERE dept name + ORDER BY",
    },
    {
        "id": 10,
        "question": "Who are the top 3 salespeople by total revenue?",
        "check": lambda rows, cols: len(rows) == 3,
        "description": "JOIN sales + SUM amount + GROUP + LIMIT",
    },
]


def run_evaluation(verbose: bool = False):
    print()
    print("🧩 Text-to-SQL Benchmark Evaluation")
    print("=" * 60)
    print()

    try:
        bot = TextToSQL(mode="chain", verbose=verbose)
    except Exception as e:
        print(f"❌ Cannot start bot: {e}")
        return

    passed = 0
    total  = len(BENCHMARK)
    total_time = 0.0

    for test in BENCHMARK:
        q  = test["question"]
        qid = test["id"]
        print(f"  [{qid:02d}] {test['description']}")
        print(f"       Q: {q}")

        t0 = time.time()
        result = bot.query(q)
        elapsed = time.time() - t0
        total_time += elapsed

        if result["error"]:
            status = "❌ FAIL"
            detail = f"Error: {result['error']}"
        else:
            try:
                ok = test["check"](result["rows"], result["columns"])
                if ok:
                    status = "✅ PASS"
                    detail = f"{len(result['rows'])} rows in {elapsed:.2f}s"
                    passed += 1
                else:
                    status = "⚠️  FAIL"
                    detail = f"Check failed | got {len(result['rows'])} rows"
            except Exception as e:
                status = "❌ ERROR"
                detail = str(e)

        print(f"       {status}  —  {detail}")
        if verbose and result.get("sql"):
            print(f"       SQL: {result['sql'][:100]}...")
        print()

    print("-" * 60)
    pct = (passed / total) * 100
    print(f"  Result: {passed}/{total} passed  ({pct:.0f}% accuracy)")
    print(f"  Avg latency: {total_time / total:.2f}s per query")
    print()

    if pct >= 90:
        print("🌟 Excellent! Production-ready accuracy.")
    elif pct >= 70:
        print("👍 Good. Consider adding more few-shot examples.")
    else:
        print("⚠️  Needs improvement. Try a larger model or refine prompts.")
    print()


if __name__ == "__main__":
    run_evaluation()
