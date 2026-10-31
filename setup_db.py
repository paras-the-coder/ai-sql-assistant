"""
setup_db.py  —  Seeds a realistic SQLite company database for Text-to-SQL demos.
Run once:  python setup_db.py
"""

import sqlite3
import os
import random
from datetime import datetime, timedelta

DB_DIR = "db"
DB_PATH = os.path.join(DB_DIR, "company.db")


def random_date(start_year=2018, end_year=2024):
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    return (start + timedelta(days=random.randint(0, delta.days))).strftime("%Y-%m-%d")


def create_database():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # ── DEPARTMENTS ──────────────────────────────────────────────────────────────
    cur.execute("DROP TABLE IF EXISTS departments")
    cur.execute("""
        CREATE TABLE departments (
            dept_id     INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            location    TEXT,
            budget      REAL,
            manager     TEXT
        )
    """)

    departments = [
        (1, "Engineering",       "Bangalore",  5000000.00, "Priya Sharma"),
        (2, "Data Science",      "Hyderabad",  3500000.00, "Arjun Mehta"),
        (3, "Product",           "Mumbai",     2500000.00, "Neha Kapoor"),
        (4, "Sales",             "Delhi",      1800000.00, "Ravi Kumar"),
        (5, "Marketing",         "Pune",       1200000.00, "Sunita Patel"),
        (6, "Human Resources",   "Chennai",     900000.00, "Deepak Nair"),
        (7, "Finance",           "Kolkata",    1500000.00, "Ankita Singh"),
    ]
    cur.executemany("INSERT INTO departments VALUES (?,?,?,?,?)", departments)

    # ── EMPLOYEES ─────────────────────────────────────────────────────────────────
    cur.execute("DROP TABLE IF EXISTS employees")
    cur.execute("""
        CREATE TABLE employees (
            emp_id      INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            email       TEXT UNIQUE,
            dept_id     INTEGER,
            role        TEXT,
            salary      REAL,
            hire_date   TEXT,
            is_active   INTEGER DEFAULT 1,
            FOREIGN KEY (dept_id) REFERENCES departments(dept_id)
        )
    """)

    employees = [
        # Engineering
        (1,  "Aarav Joshi",      "aarav@corp.io",    1, "Senior SDE",         120000, "2019-03-15", 1),
        (2,  "Ishaan Verma",     "ishaan@corp.io",   1, "SDE II",             95000,  "2020-07-01", 1),
        (3,  "Kavya Reddy",      "kavya@corp.io",    1, "SDE I",              75000,  "2022-02-10", 1),
        (4,  "Rohan Desai",      "rohan@corp.io",    1, "DevOps Engineer",    88000,  "2021-06-20", 1),
        (5,  "Meera Iyer",       "meera@corp.io",    1, "SDE I",              72000,  "2023-01-05", 1),
        # Data Science
        (6,  "Arjun Mehta",      "arjun@corp.io",    2, "Head of Data Sci.",  145000, "2018-09-12", 1),
        (7,  "Divya Krishnan",   "divya@corp.io",    2, "ML Engineer",        110000, "2020-04-22", 1),
        (8,  "Nikhil Sharma",    "nikhil@corp.io",   2, "Data Analyst",       82000,  "2021-11-30", 1),
        (9,  "Pooja Nair",       "pooja@corp.io",    2, "ML Engineer",        108000, "2022-08-14", 1),
        (10, "Raj Patel",        "raj@corp.io",      2, "Data Scientist",     98000,  "2023-03-01", 1),
        # Product
        (11, "Neha Kapoor",      "neha@corp.io",     3, "VP Product",         155000, "2017-05-10", 1),
        (12, "Aditya Bose",      "aditya@corp.io",   3, "Product Manager",    115000, "2019-10-15", 1),
        (13, "Simran Gill",      "simran@corp.io",   3, "Associate PM",       85000,  "2022-07-18", 1),
        # Sales
        (14, "Ravi Kumar",       "ravi@corp.io",     4, "Sales Head",         130000, "2018-02-28", 1),
        (15, "Priya Chatterjee", "priyac@corp.io",   4, "Account Executive",  78000,  "2020-09-05", 1),
        (16, "Sanjay Mishra",    "sanjay@corp.io",   4, "Account Executive",  76000,  "2021-03-22", 1),
        (17, "Anita Jain",       "anita@corp.io",    4, "Sales Analyst",      65000,  "2023-06-01", 1),
        # Marketing
        (18, "Sunita Patel",     "sunita@corp.io",   5, "Marketing Head",     125000, "2018-11-20", 1),
        (19, "Vikram Rao",       "vikram@corp.io",   5, "Growth Manager",     90000,  "2021-01-10", 1),
        (20, "Tanya Singh",      "tanya@corp.io",    5, "Content Strategist", 70000,  "2022-09-25", 1),
        # HR
        (21, "Deepak Nair",      "deepak@corp.io",   6, "HR Head",            118000, "2019-04-08", 1),
        (22, "Preethi Varma",    "preethi@corp.io",  6, "HR Generalist",      68000,  "2021-08-16", 1),
        # Finance
        (23, "Ankita Singh",     "ankita@corp.io",   7, "CFO",                160000, "2017-07-01", 1),
        (24, "Manish Gupta",     "manish@corp.io",   7, "Finance Analyst",    80000,  "2020-12-01", 1),
        (25, "Lata Menon",       "lata@corp.io",     7, "Accountant",         62000,  "2023-02-14", 0),  # inactive
    ]
    cur.executemany("INSERT INTO employees VALUES (?,?,?,?,?,?,?,?)", employees)

    # ── PROJECTS ──────────────────────────────────────────────────────────────────
    cur.execute("DROP TABLE IF EXISTS projects")
    cur.execute("""
        CREATE TABLE projects (
            project_id  INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            dept_id     INTEGER,
            status      TEXT,           -- 'Active','Completed','On Hold','Cancelled'
            budget      REAL,
            start_date  TEXT,
            deadline    TEXT,
            lead_emp_id INTEGER,
            FOREIGN KEY (dept_id)     REFERENCES departments(dept_id),
            FOREIGN KEY (lead_emp_id) REFERENCES employees(emp_id)
        )
    """)

    projects = [
        (1,  "AI Chatbot Platform",      2, "Active",     800000, "2024-01-10", "2024-12-31", 7),
        (2,  "Customer Analytics Dashboard", 2, "Active",  450000, "2024-03-01", "2024-09-30", 10),
        (3,  "ERP Modernisation",         1, "Active",    1200000, "2023-06-01", "2024-06-30", 1),
        (4,  "Mobile App v2.0",           1, "Completed",  600000, "2023-01-15", "2023-12-15", 2),
        (5,  "ML Recommendation Engine",  2, "Active",     550000, "2024-02-20", "2024-11-30", 9),
        (6,  "Brand Refresh",             5, "Completed",  200000, "2023-03-01", "2023-08-31", 18),
        (7,  "CRM Integration",           4, "On Hold",    350000, "2024-01-01", "2024-07-01", 14),
        (8,  "Data Warehouse Migration",  2, "Active",     900000, "2023-10-01", "2024-05-01", 8),  # overdue
        (9,  "HR Self-Service Portal",    6, "Completed",  180000, "2023-04-01", "2023-10-31", 21),
        (10, "Fraud Detection System",    2, "Active",     700000, "2024-04-01", "2025-03-31", 7),
    ]
    cur.executemany("INSERT INTO projects VALUES (?,?,?,?,?,?,?,?)", projects)

    # ── SALES ──────────────────────────────────────────────────────────────────────
    cur.execute("DROP TABLE IF EXISTS sales")
    cur.execute("""
        CREATE TABLE sales (
            sale_id     INTEGER PRIMARY KEY,
            emp_id      INTEGER,
            amount      REAL,
            sale_date   TEXT,
            product     TEXT,
            region      TEXT,
            FOREIGN KEY (emp_id) REFERENCES employees(emp_id)
        )
    """)

    random.seed(42)
    products = ["Enterprise License", "Pro Plan", "Starter Pack", "Add-on Module", "Support Contract"]
    regions  = ["North", "South", "East", "West", "Central"]
    sales_data = []
    sale_id = 1
    for emp_id in [14, 15, 16, 17]:  # Sales team
        for _ in range(random.randint(12, 20)):
            sales_data.append((
                sale_id,
                emp_id,
                round(random.uniform(5000, 80000), 2),
                random_date(2023, 2024),
                random.choice(products),
                random.choice(regions),
            ))
            sale_id += 1
    cur.executemany("INSERT INTO sales VALUES (?,?,?,?,?,?)", sales_data)

    conn.commit()
    conn.close()
    print(f"✅  Database created at: {DB_PATH}")
    print(f"    Tables: departments ({len(departments)} rows), employees ({len(employees)} rows),")
    print(f"            projects ({len(projects)} rows), sales ({len(sales_data)} rows)")


if __name__ == "__main__":
    create_database()
