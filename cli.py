"""
cli.py  —  Interactive command-line interface for the Text-to-SQL assistant.
Run:  python cli.py
"""

import sys
import os
from text_to_sql import TextToSQL

BANNER = """
┌────────────────────────────────────────────────────────────────────────┐
│   🧠  Text-to-SQL Assistant   |   Powered by LangChain + Groq         │
└────────────────────────────────────────────────────────────────────────┘

Type a question in plain English to query the database.
Special commands:
  :help     — show example questions
  :schema   — print database schema
  :history  — show query history
  :clear    — clear history
  :quit     — exit
"""

EXAMPLES = """
Example questions to try:
  • How many employees are in each department?
  • Who are the top 3 highest paid employees?
  • List all employees hired after 2022
  • What is the average salary by department?
  • Which projects are overdue?
  • Show all active projects with their lead and budget
  • Who are the top 3 salespeople by total revenue?
  • How many employees earn more than 100000?
  • Which department has the highest total payroll?
  • List Engineering employees sorted by salary descending
"""


def print_result(result: dict):
    print()
    if result["error"]:
        print(f"  ❌ Error: {result['error']}")
        return

    if result.get("sql"):
        print("  Generated SQL:")
        print("  " + "-" * 60)
        for line in result["sql"].splitlines():
            print(f"  {line}")
        print("  " + "-" * 60)

    if result.get("table") and result["rows"]:
        print()
        print("  Results:")
        for line in result["table"].splitlines():
            print(f"  {line}")

    print()
    print(f"  💡 Answer: {result['answer']}")
    print()


def main():
    print(BANNER)

    try:
        bot = TextToSQL(verbose=False)
        print("  ✅ Connected to database. Ready to query!\n")
    except Exception as e:
        print(f"  ❌ Startup error: {e}")
        sys.exit(1)

    from utils import get_db_schema

    while True:
        try:
            user_input = input("❓ You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Bye! ")
            break

        if not user_input:
            continue

        if user_input.lower() in (":quit", ":q", "exit"):
            print("  Bye! ")
            break
        elif user_input.lower() == ":help":
            print(EXAMPLES)
        elif user_input.lower() == ":schema":
            print("\n" + get_db_schema(bot.db_path) + "\n")
        elif user_input.lower() == ":history":
            history = bot.get_history()
            if not history:
                print("  No history yet.")
            else:
                for i, h in enumerate(history, 1):
                    print(f"  {i}. Q: {h['q']}")
                    print(f"     A: {h['answer']}")
            print()
        elif user_input.lower() == ":clear":
            bot.clear_history()
            print("  History cleared.")
        else:
            print("  Thinking...")
            result = bot.query(user_input)
            print_result(result)


if __name__ == "__main__":
    main()
