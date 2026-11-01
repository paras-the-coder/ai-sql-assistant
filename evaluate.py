"""
evaluate.py  —  Comprehensive Benchmark Evaluation Suite for Text-to-SQL.
Run:  python evaluate.py [--no-retry] [--limit N] [--verbose]

Measures chain-mode execution accuracy: the generated SQL's result set is compared with
the result of a hand-written gold query. Reports per-category accuracy with a 95% Wilson
interval, latency and failure types. Use --no-retry to measure the retry loop's effect.
(Agent mode is not benchmarked: it returns prose, not a SQL result set.)
"""

import sys
import time
import argparse
from collections import Counter, defaultdict
from tabulate import tabulate

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from text_to_sql import TextToSQL
from utils import execute_query, compare_result_sets

# ---------------------------------------------------------------------------
# Benchmark Dataset (35 independent questions across 5 categories)
# Note: None of these are included in the few-shot prompt demonstrations.
# ---------------------------------------------------------------------------
BENCHMARK_DATASET = [
    # ── 1. Aggregation (7 queries) ──────────────────────────────────────────
    {
        "id": 1,
        "category": "Aggregation",
        "question": "How many inactive employees are in the company?",
        "gold_sql": "SELECT COUNT(*) FROM employees WHERE is_active = 0;",
    },
    {
        "id": 2,
        "category": "Aggregation",
        "question": "What is the total budget allocated across all departments?",
        "gold_sql": "SELECT SUM(budget) FROM departments;",
    },
    {
        "id": 3,
        "category": "Aggregation",
        "question": "What is the average salary of active employees?",
        "gold_sql": "SELECT ROUND(AVG(salary), 2) FROM employees WHERE is_active = 1;",
    },
    {
        "id": 4,
        "category": "Aggregation",
        "question": "What is the salary difference between the highest and lowest paid active employee?",
        "gold_sql": "SELECT MAX(salary) - MIN(salary) FROM employees WHERE is_active = 1;",
    },
    {
        "id": 5,
        "category": "Aggregation",
        "question": "How many distinct office locations do departments operate in?",
        "gold_sql": "SELECT COUNT(DISTINCT location) FROM departments;",
    },
    {
        "id": 6,
        "category": "Aggregation",
        "question": "How many projects have been marked with status Completed?",
        "gold_sql": "SELECT COUNT(*) FROM projects WHERE status = 'Completed';",
    },
    {
        "id": 7,
        "category": "Aggregation",
        "question": "What is the total revenue amount generated across all sales?",
        "gold_sql": "SELECT ROUND(SUM(amount), 2) FROM sales;",
    },

    # ── 2. Multi-Table JOIN (7 queries) ────────────────────────────────────
    {
        "id": 8,
        "category": "Join",
        "question": "List all employees located in Bangalore with their department name.",
        "gold_sql": """
            SELECT e.name, d.name 
            FROM employees e 
            JOIN departments d ON e.dept_id = d.dept_id 
            WHERE d.location = 'Bangalore';
        """,
    },
    {
        "id": 9,
        "category": "Join",
        "question": "Show all active project names and the name of their project lead.",
        "gold_sql": """
            SELECT p.name, e.name 
            FROM projects p 
            JOIN employees e ON p.lead_emp_id = e.emp_id 
            WHERE p.status = 'Active';
        """,
    },
    {
        "id": 10,
        "category": "Join",
        "question": "Which departments have projects with a budget greater than 500000?",
        "gold_sql": """
            SELECT DISTINCT d.name 
            FROM departments d 
            JOIN projects p ON d.dept_id = p.dept_id 
            WHERE p.budget > 500000;
        """,
    },
    {
        "id": 11,
        "category": "Join",
        "question": "Who is the department manager for the employee with the role Data Analyst?",
        "gold_sql": """
            SELECT e.name, d.manager 
            FROM employees e 
            JOIN departments d ON e.dept_id = d.dept_id 
            WHERE e.role = 'Data Analyst';
        """,
    },
    {
        "id": 12,
        "category": "Join",
        "question": "List distinct employee names who closed sales in the North region.",
        "gold_sql": """
            SELECT DISTINCT e.name 
            FROM employees e 
            JOIN sales s ON e.emp_id = s.emp_id 
            WHERE s.region = 'North';
        """,
    },
    {
        "id": 13,
        "category": "Join",
        "question": "What department location is the ERP Modernisation project associated with?",
        "gold_sql": """
            SELECT d.location 
            FROM projects p 
            JOIN departments d ON p.dept_id = d.dept_id 
            WHERE p.name = 'ERP Modernisation';
        """,
    },
    {
        "id": 14,
        "category": "Join",
        "question": "Show employee names and products sold for sales transactions above 60000.",
        "gold_sql": """
            SELECT e.name, s.product 
            FROM employees e 
            JOIN sales s ON e.emp_id = s.emp_id 
            WHERE s.amount > 60000;
        """,
    },

    # ── 3. Date & Temporal Logic (7 queries) ──────────────────────────────
    {
        "id": 15,
        "category": "Date Filter",
        "question": "List active employees hired before the year 2020.",
        "gold_sql": "SELECT name, hire_date FROM employees WHERE hire_date < '2020-01-01' AND is_active = 1;",
    },
    {
        "id": 16,
        "category": "Date Filter",
        "question": "Which projects have a deadline in 2025 or later?",
        "gold_sql": "SELECT name, deadline FROM projects WHERE deadline >= '2025-01-01';",
    },
    {
        "id": 17,
        "category": "Date Filter",
        "question": "Which projects started in the first half of 2024?",
        "gold_sql": "SELECT name, start_date FROM projects WHERE start_date BETWEEN '2024-01-01' AND '2024-06-30';",
    },
    {
        "id": 18,
        "category": "Date Filter",
        "question": "How many sales transactions took place in the year 2024?",
        "gold_sql": "SELECT COUNT(*) FROM sales WHERE sale_date BETWEEN '2024-01-01' AND '2024-12-31';",
    },
    {
        "id": 19,
        "category": "Date Filter",
        "question": "List all employees who were hired during 2021.",
        "gold_sql": "SELECT name, hire_date FROM employees WHERE hire_date LIKE '2021%';",
    },
    {
        "id": 20,
        "category": "Date Filter",
        "question": "Find active projects with a deadline after 2024-09-30.",
        "gold_sql": "SELECT name, deadline FROM projects WHERE status = 'Active' AND deadline > '2024-09-30';",
    },
    {
        "id": 21,
        "category": "Date Filter",
        "question": "What is the total sales amount logged before 2024?",
        "gold_sql": "SELECT ROUND(SUM(amount), 2) FROM sales WHERE sale_date < '2024-01-01';",
    },

    # ── 4. Grouping & Ranking (7 queries) ──────────────────────────────────
    {
        "id": 22,
        "category": "Ranking",
        "question": "Who is the lowest paid active employee in the company?",
        "gold_sql": "SELECT name, salary FROM employees WHERE is_active = 1 ORDER BY salary ASC LIMIT 1;",
    },
    {
        "id": 23,
        "category": "Ranking",
        "question": "Which department has the highest total payroll for active staff?",
        "gold_sql": """
            SELECT d.name, SUM(e.salary) AS total_payroll 
            FROM departments d 
            JOIN employees e ON d.dept_id = e.dept_id 
            WHERE e.is_active = 1 
            GROUP BY d.name 
            ORDER BY total_payroll DESC 
            LIMIT 1;
        """,
    },
    {
        "id": 24,
        "category": "Ranking",
        "question": "Which sales region generated the highest total revenue?",
        "gold_sql": """
            SELECT region, ROUND(SUM(amount), 2) AS total_revenue 
            FROM sales 
            GROUP BY region 
            ORDER BY total_revenue DESC 
            LIMIT 1;
        """,
    },
    {
        "id": 25,
        "category": "Ranking",
        "question": "What is the most frequently sold product by transaction count?",
        "gold_sql": """
            SELECT product, COUNT(*) AS count 
            FROM sales 
            GROUP BY product 
            ORDER BY count DESC 
            LIMIT 1;
        """,
    },
    {
        "id": 26,
        "category": "Ranking",
        "question": "Top 3 highest budget projects?",
        "gold_sql": "SELECT name, budget FROM projects ORDER BY budget DESC LIMIT 3;",
    },
    {
        "id": 27,
        "category": "Ranking",
        "question": "Who are the top 3 salespeople by total sales revenue?",
        "gold_sql": """
            SELECT e.name, ROUND(SUM(s.amount), 2) AS revenue 
            FROM employees e 
            JOIN sales s ON e.emp_id = s.emp_id 
            GROUP BY e.emp_id, e.name 
            ORDER BY revenue DESC 
            LIMIT 3;
        """,
    },
    {
        "id": 28,
        "category": "Ranking",
        "question": "Count of projects per department name sorted descending.",
        "gold_sql": """
            SELECT d.name, COUNT(p.project_id) AS p_count 
            FROM departments d 
            LEFT JOIN projects p ON d.dept_id = p.dept_id 
            GROUP BY d.name 
            ORDER BY p_count DESC;
        """,
    },

    # ── 5. Multi-Condition & Business Logic (7 queries) ───────────────────
    {
        "id": 29,
        "category": "Multi-Condition",
        "question": "List Engineering department employees earning at least 90000.",
        "gold_sql": "SELECT name, role, salary FROM employees WHERE salary >= 90000 AND dept_id = 1;",
    },
    {
        "id": 30,
        "category": "Multi-Condition",
        "question": "List departments with a budget over 2000000 not located in Bangalore.",
        "gold_sql": "SELECT name FROM departments WHERE budget > 2000000 AND location != 'Bangalore';",
    },
    {
        "id": 31,
        "category": "Multi-Condition",
        "question": "Find active projects with a budget under 600000.",
        "gold_sql": "SELECT name, budget FROM projects WHERE status = 'Active' AND budget < 600000;",
    },
    {
        "id": 32,
        "category": "Multi-Condition",
        "question": "Distinct products sold in the Central region with amount greater than 40000.",
        "gold_sql": "SELECT DISTINCT product FROM sales WHERE region = 'Central' AND amount > 40000;",
    },
    {
        "id": 33,
        "category": "Multi-Condition",
        "question": "Employees in Data Science department with salary over 100000.",
        "gold_sql": """
            SELECT e.name, e.salary 
            FROM employees e 
            JOIN departments d ON e.dept_id = d.dept_id 
            WHERE d.name = 'Data Science' AND e.salary > 100000;
        """,
    },
    {
        "id": 34,
        "category": "Multi-Condition",
        "question": "How many Enterprise License sales were closed with amount above 20000?",
        "gold_sql": "SELECT COUNT(*) FROM sales WHERE product = 'Enterprise License' AND amount > 20000;",
    },
    {
        "id": 35,
        "category": "Multi-Condition",
        "question": "Active leadership personnel whose role includes Head, VP, or CFO.",
        "gold_sql": """
            SELECT name, role 
            FROM employees 
            WHERE is_active = 1 
              AND (role LIKE '%Head%' OR role LIKE '%VP%' OR role LIKE '%CFO%');
        """,
    },
]


def wilson_interval(passed: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a pass rate (reliable at small n, unlike the normal approximation)."""
    if total == 0:
        return 0.0, 0.0
    p = passed / total
    denom = 1 + z**2 / total
    centre = (p + z**2 / (2 * total)) / denom
    half = z * (p * (1 - p) / total + z**2 / (4 * total**2)) ** 0.5 / denom
    return centre - half, centre + half


def run_benchmark(max_retries: int = 1, limit: int | None = None, verbose: bool = False):
    print("\n" + "=" * 70)
    print(f"📊 Text-to-SQL Benchmark  |  chain mode  |  retries: {max_retries}")
    print("=" * 70 + "\n")

    try:
        bot = TextToSQL(mode="chain", max_retries=max_retries, verbose=verbose)
    except Exception as e:
        print(f"❌ Failed to initialize TextToSQL: {e}")
        sys.exit(1)

    # Run every gold query first; a benchmark item with an erroring or empty gold answer is invalid
    # (an empty gold result would "pass" any query that also returns nothing), so it is excluded.
    dataset = []
    for item in BENCHMARK_DATASET[:limit]:
        try:
            gold_rows, _ = execute_query(bot.db_path, item["gold_sql"])
        except Exception as e:
            print(f"  [Q{item['id']:02d}] ⚠️ Skipped, gold SQL failed: {e}")
            continue
        if not gold_rows:
            print(f"  [Q{item['id']:02d}] ⚠️ Skipped, gold SQL returns no rows")
            continue
        dataset.append((item, gold_rows))

    total_queries = len(dataset)
    passed_queries = 0
    total_latency = 0.0
    retried = 0
    category_stats = defaultdict(lambda: {"total": 0, "passed": 0, "latency": 0.0})
    failures = []

    for item, gold_rows in dataset:
        qid, cat, question = item["id"], item["category"], item["question"]
        category_stats[cat]["total"] += 1

        t0 = time.time()
        result = bot.query(question, generate_answer=False)
        latency = time.time() - t0
        total_latency += latency
        retried += bool(result.get("retries"))
        category_stats[cat]["latency"] += latency

        if result["error"]:
            kind, is_correct = "pipeline error", False
            fail_reason = f"Pipeline Error: {result['error']}"
        elif not result.get("rows"):
            kind, is_correct = "empty result", False
            fail_reason = "Empty result set returned"
        else:
            is_correct = compare_result_sets(gold_rows, result["rows"])
            kind = "wrong result"
            fail_reason = f"Mismatch: expected {len(gold_rows)} rows, got {len(result['rows'])}"

        print(f"  [{qid:02d}] [{cat:15s}] {'✅ PASS' if is_correct else '❌ FAIL'} ({latency:.2f}s) — {question[:55]}...", flush=True)
        time.sleep(0.3)  # stay under API rate limits

        if is_correct:
            passed_queries += 1
            category_stats[cat]["passed"] += 1
        else:
            failures.append({
                "id": qid, "category": cat, "kind": kind, "question": question,
                "gold_sql": item["gold_sql"].strip(), "gen_sql": result.get("sql", "").strip(),
                "reason": fail_reason,
            })

    if not total_queries:
        print("No valid benchmark questions to run.")
        return 0.0, 0.0

    overall_pct = passed_queries / total_queries * 100
    avg_latency = total_latency / total_queries
    low, high = wilson_interval(passed_queries, total_queries)

    print("\n" + "-" * 70)
    summary_rows = [
        [cat, d["passed"], d["total"], f"{d['passed'] / d['total'] * 100:.1f}%", f"{d['latency'] / d['total']:.2f}s"]
        for cat, d in sorted(category_stats.items())
    ]
    print(tabulate(summary_rows, headers=["Category", "Passed", "Total", "Accuracy", "Avg Latency"], tablefmt="rounded_outline"))

    print("\n" + "=" * 70)
    print(f"🏆 Execution accuracy: {passed_queries}/{total_queries} ({overall_pct:.1f}%)  |  95% CI: {low * 100:.0f}%–{high * 100:.0f}%")
    print(f"⚡ Avg latency (SQL generation + execution, incl. retries): {avg_latency:.2f}s")
    print(f"🔁 Retry loop fired on {retried}/{total_queries} questions")
    if failures:
        print("❌ Failures by type: " + ", ".join(f"{k}: {v}" for k, v in Counter(f["kind"] for f in failures).items()))
    print("=" * 70 + "\n")

    if failures and verbose:
        print("Failure diagnostics:")
        for f in failures:
            print(f"\n[Q{f['id']:02d} - {f['category']} - {f['kind']}] {f['question']}")
            print(f"  Reason:   {f['reason']}")
            print(f"  Gold SQL: {f['gold_sql']}")
            print(f"  Gen  SQL: {f['gen_sql']}")
        print()

    return overall_pct, avg_latency


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Text-to-SQL benchmark (chain mode).")
    parser.add_argument("--no-retry", action="store_true", help="Disable the SQL-error retry loop (for ablation)")
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N questions")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print gold vs generated SQL for failures")
    args = parser.parse_args()

    run_benchmark(max_retries=0 if args.no_retry else 1, limit=args.limit, verbose=args.verbose)