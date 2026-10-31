"""
text_to_sql.py  —  Core Text-to-SQL engine using LangChain + Groq.
"""

import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate, FewShotPromptTemplate
from langchain_core.output_parsers import StrOutputParser  
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain.agents import AgentType

from prompts import FEW_SHOT_EXAMPLES, ANSWER_PROMPT_TEMPLATE, SQL_SYSTEM_PROMPT
from utils import (
    get_db_schema,
    execute_query,
    format_results,
    extract_sql,
    validate_sql,
    results_to_string,
    check_db_exists,
)

load_dotenv()


class TextToSQL:
    """
    End-to-end Text-to-SQL pipeline.

    Two modes:
    - 'chain'  : fast, deterministic SQL generation via a custom LangChain chain.
    - 'agent'  : LangChain SQL agent that can introspect schema, retry errors, etc.
    """

    def __init__(
        self,
        db_path: str | None = None,
        mode: str = "chain",  # 'chain' | 'agent'
        model: str | None = None,
        verbose: bool = False,
    ):
        load_dotenv()

        self.db_path = db_path or os.getenv("DB_PATH", "db/company.db")
        self.mode    = mode
        self.verbose = verbose or (os.getenv("DEBUG", "false").lower() == "true")

        if not check_db_exists(self.db_path):
            raise FileNotFoundError(
                f"Database not found at '{self.db_path}'.\n"
                "Run `python setup_db.py` first."
            )

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY not set.\nCopy .env.example to .env and add your key."
            )

        model_name = model or os.getenv("GROQ_MODEL", "llama3-70b-8192")

        # --- LLM ----------------------------------------------------------
        self.llm = ChatGroq(
            model=model_name,
            api_key=api_key,
            temperature=0,        # deterministic SQL
            max_tokens=1024,
        )

        # --- Schema -------------------------------------------------------
        self.schema = get_db_schema(self.db_path)

        # --- Mode-specific setup ------------------------------------------
        if self.mode == "agent":
            self._setup_agent()
        else:
            self._setup_chain()

        # Conversation memory (simple list for multi-turn)
        self.history: list[dict] = []

    # ------------------------------------------------------------------
    # Chain mode
    # ------------------------------------------------------------------
    def _setup_chain(self):
        """Build a custom few-shot prompt chain for SQL generation using LCEL."""

        # Few-shot example formatter
        example_prompt = PromptTemplate(
            input_variables=["question", "sql"],
            template="Question: {question}\nSQL:\n{sql}",
        )

        few_shot_prompt = FewShotPromptTemplate(
            examples=FEW_SHOT_EXAMPLES,
            example_prompt=example_prompt,
            prefix=SQL_SYSTEM_PROMPT,
            suffix="Question: {question}\nSQL:",
            input_variables=["question", "schema"],
        )

        # Configured with LCEL pipelines (piping prompt -> model -> parser)
        self.sql_chain = few_shot_prompt | self.llm | StrOutputParser()
        self.answer_chain = ANSWER_PROMPT_TEMPLATE | self.llm | StrOutputParser()

    def _setup_agent(self):
        """Build a LangChain SQL Agent with read-only database lockdown."""
        abs_path = os.path.abspath(self.db_path).replace("\\", "/")
        db = SQLDatabase.from_uri(f"sqlite:///file:{abs_path}?mode=ro&uri=true")
        toolkit = SQLDatabaseToolkit(db=db, llm=self.llm)
        self.agent = create_sql_agent(
            llm=self.llm,
            toolkit=toolkit,
            agent_type="tool-calling",
            verbose=self.verbose,
            agent_executor_kwargs={"handle_parsing_errors": True},
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def query(self, question: str, generate_answer: bool = True) -> dict:
        """
        Main entry point.

        Returns a dict with keys:
          question   : original question
          sql        : generated SQL
          rows       : raw result rows (list of tuples)
          columns    : column names
          table      : pretty-printed table string
          answer     : LLM-generated natural language answer
          error      : error message if something failed (else None)
        """
        result = {
            "question": question,
            "sql":      "",
            "rows":     [],
            "columns":  [],
            "table":    "",
            "answer":   "",
            "error":    None,
        }

        if not question or not question.strip():
            result["error"] = "Question cannot be empty."
            result["answer"] = "Please ask a valid question."
            return result

        if len(question) > 500:
            result["error"] = "Question too long (max 500 characters)."
            result["answer"] = "Please keep your question under 500 characters."
            return result

        try:
            if self.mode == "agent":
                return self._query_agent(question, result)
            else:
                return self._query_chain(question, result, generate_answer=generate_answer)
        except Exception as e:
            result["error"] = str(e)
            result["answer"] = f"Sorry, I encountered an error: {e}"
            return result

    def _query_chain(self, question: str, result: dict, max_retries: int = 1, generate_answer: bool = True) -> dict:
        current_question = question
        last_error = ""

        for attempt in range(max_retries + 1):
            # 1. Generate SQL via .invoke()
            raw_sql = self.sql_chain.invoke({
                "question": current_question,
                "schema": self.schema,
            })
            sql = extract_sql(raw_sql)

            # 2. Validate (read-only guard)
            ok, reason = validate_sql(sql)
            if not ok:
                result["error"]  = reason
                result["answer"] = reason
                result["sql"]    = ""  # Clear generated SQL on validation failure!
                return result

            result["sql"] = sql

            # 3. Execute with automatic retry on SQL syntax/runtime errors
            try:
                rows, cols = execute_query(self.db_path, sql)
                break
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    current_question = (
                        f"{question}\n"
                        f"-- Note: Previous attempt produced `{sql}` which failed with: {last_error}. "
                        f"Please fix the error and output valid SQLite."
                    )
                else:
                    result["error"] = f"Execution error: {last_error}"
                    result["answer"] = f"Failed to execute query: {last_error}"
                    return result

        result["rows"]    = rows
        result["columns"] = cols
        result["table"]   = format_results(rows, cols)

        # 4. Natural language answer via .invoke()
        if generate_answer:
            sql_result_str = results_to_string(rows, cols)
            answer = self.answer_chain.invoke({
                "question": question,
                "sql_query": sql,
                "sql_result": sql_result_str,
            })
            result["answer"] = answer.strip()
        else:
            result["answer"] = ""

        # 5. Save to history
        self.history.append({"q": question, "sql": sql, "answer": result["answer"]})
        return result

    def _query_agent(self, question: str, result: dict) -> dict:
        raw_output = self.agent.invoke({"input": question})
        answer_text = (
            raw_output.get("output", str(raw_output))
            if isinstance(raw_output, dict)
            else str(raw_output)
        )
        result["answer"] = answer_text
        self.history.append({"q": question, "answer": answer_text})
        return result

    def get_history(self) -> list[dict]:
        return self.history

    def clear_history(self):
        self.history = []
