"""
app.py  —  Streamlit web UI for the Text-to-SQL assistant.
Run:  streamlit run app.py
"""

import html
import streamlit as st
from text_to_sql import TextToSQL
from utils import get_db_schema

# ---- Page config ----------------------------------------------------------
st.set_page_config(
    page_title="Text-to-SQL | AI Assistant",
    page_icon="🧠",
    layout="wide",
)

# ---- Custom CSS -----------------------------------------------------------
st.markdown("""
<style>
.sql-box {
    background: #1e1e2e;
    color: #cdd6f4;
    border-radius: 8px;
    padding: 12px 16px;
    font-family: 'Courier New', monospace;
    font-size: 13px;
    white-space: pre-wrap;
    border: 1px solid #313244;
    margin: 8px 0;
}
.answer-box {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-left: 4px solid #6c63ff;
    border-radius: 4px;
    padding: 12px 16px;
    color: #e8e8f0;
    font-size: 15px;
    margin: 8px 0;
}
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
    margin-right: 6px;
}
.badge-green  { background: #1a472a; color: #5cb85c; }
.badge-blue   { background: #0d2137; color: #5bc0de; }
.badge-orange { background: #3b2a00; color: #f0ad4e; }
</style>
""", unsafe_allow_html=True)

# ---- Sidebar ---------------------------------------------------------------
with st.sidebar:
    st.title("🧠 Text-to-SQL")
    st.caption("Powered by LangChain · Groq · SQLite")
    st.divider()

    mode = st.radio(
        "Engine Mode",
        options=["chain", "agent"],
        help="chain = fast & deterministic | agent = smarter, handles errors",
    )

    model = st.selectbox(
    "Groq Model",
    options=["openai/gpt-oss-120b"],
    index=0,
    )

    show_sql = st.toggle("Show SQL query", value=True)
    show_table = st.toggle("Show raw table", value=True)

    st.divider()
    st.markdown("""
    **Sample questions:**
    - How many employees per department?
    - Top 3 highest paid employees?
    - Which projects are overdue?
    - Average salary by department?
    - Who are the top salespeople?
    """)

    if st.button("🗑️ Clear chat history"):
        st.session_state.messages = []
        if "bot" in st.session_state:
            st.session_state.bot.clear_history()
        st.rerun()

    with st.expander("🗃️ Database schema"):
        try:
            schema = get_db_schema("db/company.db")
            st.code(schema, language="sql")
        except Exception:
            st.warning("Run `python setup_db.py` first.")

# ---- Main ------------------------------------------------------------------
st.title("💬 Ask Your Database Anything")
st.caption("Type a question in plain English — I’ll write the SQL and answer it.")

# Init session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "bot" not in st.session_state or st.session_state.get("bot_mode") != mode:
    with st.spinner("🔄 Loading model..."):
        try:
            st.session_state.bot = TextToSQL(mode=mode, model=model)
            st.session_state.bot_mode = mode
        except Exception as e:
            st.error(f"❌ {e}")
            st.stop()

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.write(msg["content"])
        else:
            if show_sql and msg.get("sql"):
                st.markdown("**📝 Generated SQL**")
                st.markdown(f'<div class="sql-box">{html.escape(msg["sql"])}</div>',
                            unsafe_allow_html=True)
            if show_table and msg.get("table"):
                st.markdown("**📊 Results**")
                st.code(msg["table"])
            st.markdown(f'<div class="answer-box">💡 {html.escape(msg["answer"])}</div>',
                        unsafe_allow_html=True)

# Chat input
if question := st.chat_input("e.g. Which Engineering employees earn more than 80000?"):
    # User bubble
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    # Assistant bubble
    with st.chat_message("assistant"):
        with st.spinner("⏳ Running query..."):
            result = st.session_state.bot.query(question)

        if result.get("error"):
            st.warning(f"🛡️ Guardrail Blocked: {result['error']}")
        else:
            if show_sql and result.get("sql"):
                st.markdown("**📝 Generated SQL**")
                st.markdown(f'<div class="sql-box">{html.escape(result["sql"])}</div>', unsafe_allow_html=True)
            if show_table and result.get("table"):
                st.markdown("**📊 Results**")
                st.code(result["table"])
            st.markdown(
                f'<div class="answer-box">💡 {html.escape(result["answer"])}</div>', unsafe_allow_html=True
            )
        # Save to history
        st.session_state.messages.append({
            "role":    "assistant",
            "sql":     result.get("sql", ""),
            "table":   result.get("table", ""),
            "answer":  result.get("answer", result.get("error", "")),
        })
