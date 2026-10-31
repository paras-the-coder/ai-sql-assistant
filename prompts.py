"""
prompts.py  —  Custom prompt templates for the Text-to-SQL pipeline.
"""

from langchain_core.prompts import PromptTemplate

# ---------------------------------------------------------------------------
# System prompt: instructs the LLM how to behave as a SQL generator
# ---------------------------------------------------------------------------
SQL_SYSTEM_PROMPT = """
You are an expert SQL assistant for a corporate SQLite database.

Database schema:
{schema}

Rules you MUST follow:
1. Generate ONLY valid SQLite SQL. No PostgreSQL / MySQL-specific syntax.
2. Always use table aliases (e.g. e for employees, d for departments).
3. For aggregation questions, use GROUP BY correctly.
4. Use LOWER() for case-insensitive text comparisons.
5. Prefer JOINs over subqueries when both work.
6. Limit results to 20 rows by default unless the user specifies otherwise.
7. Never use SELECT * — always list column names explicitly.
8. If a question is ambiguous, make a reasonable assumption and state it.
9. Return ONLY the SQL query, no explanation.
"""

# ---------------------------------------------------------------------------
# Few-shot examples to dramatically improve accuracy
# ---------------------------------------------------------------------------
FEW_SHOT_EXAMPLES = [
    {
        "question": "How many employees are in each department?",
        "sql": """
SELECT d.name AS department, COUNT(e.emp_id) AS headcount
FROM employees e
JOIN departments d ON e.dept_id = d.dept_id
WHERE e.is_active = 1
GROUP BY d.name
ORDER BY headcount DESC;
        """.strip(),
    },
    {
        "question": "Who are the top 3 highest paid employees?",
        "sql": """
SELECT e.name, e.role, e.salary, d.name AS department
FROM employees e
JOIN departments d ON e.dept_id = d.dept_id
WHERE e.is_active = 1
ORDER BY e.salary DESC
LIMIT 3;
        """.strip(),
    },
    {
        "question": "Which projects are overdue?",
        "sql": """
SELECT p.name AS project, p.deadline, p.status, e.name AS lead
FROM projects p
JOIN employees e ON p.lead_emp_id = e.emp_id
WHERE p.status = 'Active'
  AND p.deadline < DATE('now')
ORDER BY p.deadline ASC;
        """.strip(),
    },
    {
        "question": "What is the average salary by department?",
        "sql": """
SELECT d.name AS department,
       ROUND(AVG(e.salary), 2) AS avg_salary,
       COUNT(e.emp_id) AS headcount
FROM employees e
JOIN departments d ON e.dept_id = d.dept_id
WHERE e.is_active = 1
GROUP BY d.name
ORDER BY avg_salary DESC;
        """.strip(),
    },
    {
        "question": "List all employees hired after 2022",
        "sql": """
SELECT e.name, e.role, e.hire_date, d.name AS department
FROM employees e
JOIN departments d ON e.dept_id = d.dept_id
WHERE e.hire_date > '2022-12-31'
ORDER BY e.hire_date ASC;
        """.strip(),
    },
]

# ---------------------------------------------------------------------------
# Answer formatting prompt
# ---------------------------------------------------------------------------
ANSWER_PROMPT_TEMPLATE = PromptTemplate(
    input_variables=["question", "sql_query", "sql_result"],
    template="""
You are a helpful data analyst. A user asked a question, SQL was run, and you got the results.
Summarise the results in 1–3 concise sentences in plain English.

User question : {question}
SQL executed  : {sql_query}
SQL results   : {sql_result}

Answer in plain English (no markdown, no bullet points):
    """,
)
