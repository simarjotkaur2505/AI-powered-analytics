"""
AI-Powered SQL Analytics Dashboard
Entry point: streamlit run app.py
"""

import logging
import os
import sys
from pathlib import Path

# ── Logging setup (runs before any module import) ─────────────────────────────
LOG_PATH = Path(os.getenv("LOG_PATH", "logs/app.log"))
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ── Third-party imports ───────────────────────────────────────────────────────
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from src.ai import generate_insight, text_to_sql
from src.charts import pick_chart_type, render_chart
from src.db import execute_query

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    /* ---- Global font ---- */
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* ---- Header gradient ---- */
    .hero {
        background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%);
        border-radius: 16px;
        padding: 2rem 2.5rem;
        color: white;
        margin-bottom: 1.5rem;
    }
    .hero h1 { font-size: 2rem; font-weight: 700; margin: 0 0 0.4rem; }
    .hero p  { opacity: 0.88; margin: 0; font-size: 1.05rem; }

    /* ---- Cards ---- */
    .card {
        background: white;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 1rem;
    }
    .card-title {
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #6B7280;
        margin-bottom: 0.6rem;
    }

    /* ---- Example button pills ---- */
    div[data-testid="stHorizontalBlock"] .stButton button {
        border-radius: 999px;
        border: 1px solid #D1D5DB;
        background: white;
        color: #374151;
        font-size: 0.82rem;
        padding: 0.3rem 0.9rem;
        transition: all 0.15s;
    }
    div[data-testid="stHorizontalBlock"] .stButton button:hover {
        border-color: #6366F1;
        color: #6366F1;
        background: #F5F3FF;
    }

    /* ---- Insight bullets ---- */
    .insight-box {
        background: #F5F3FF;
        border-left: 4px solid #6366F1;
        border-radius: 0 10px 10px 0;
        padding: 1rem 1.2rem;
        font-size: 0.95rem;
        line-height: 1.7;
    }

    /* ---- SQL code block ---- */
    .stCode { border-radius: 10px; }

    /* ---- Editable SQL textarea ---- */
    textarea[data-testid="stTextArea"] {
        font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace !important;
        font-size: 0.88rem !important;
        background: #1E1E2E !important;
        color: #CDD6F4 !important;
        border: 1px solid #313244 !important;
        border-radius: 10px !important;
    }
    .sql-badge {
        display: inline-block;
        font-size: 0.72rem;
        font-weight: 600;
        padding: 0.15rem 0.55rem;
        border-radius: 999px;
        margin-left: 0.5rem;
        vertical-align: middle;
    }
    .badge-ai    { background: #EDE9FE; color: #6D28D9; }
    .badge-edited { background: #FEF3C7; color: #B45309; }

    /* ---- Metric card ---- */
    div[data-testid="stMetric"] {
        background: white;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 1rem 1.4rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Example questions ─────────────────────────────────────────────────────────

EXAMPLES = [
    "Top 5 customers by revenue",
    "Monthly revenue trend last 12 months",
    "Revenue by product category",
    "Return rate by country",
    "New customers per month",
    "Average order value by segment",
]

# ── Session state ─────────────────────────────────────────────────────────────

if "question" not in st.session_state:
    st.session_state.question = ""
if "history" not in st.session_state:
    st.session_state.history = []           # list of {question, sql, insight}
if "generated_sql" not in st.session_state:
    st.session_state.generated_sql = None   # SQL waiting to be executed
if "pending_question" not in st.session_state:
    st.session_state.pending_question = ""  # question that produced generated_sql


# ── Hero ──────────────────────────────────────────────────────────────────────

st.markdown(
    """
    <div class="hero">
        <h1>📊 AI Analytics Dashboard</h1>
        <p>Ask a question in plain English — get SQL, results, a chart, and AI insights instantly.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Input area ────────────────────────────────────────────────────────────────

col_input, col_btn = st.columns([5, 1])
with col_input:
    question = st.text_input(
        label="Your question",
        placeholder='e.g. "Show me top 5 customers by revenue last month"',
        value=st.session_state.question,
        label_visibility="collapsed",
    )
with col_btn:
    run_clicked = st.button("Run →", type="primary", use_container_width=True)

# ── Example pills ─────────────────────────────────────────────────────────────

st.markdown("<p style='color:#6B7280;font-size:0.82rem;margin:0.3rem 0 0.5rem'>Try an example:</p>", unsafe_allow_html=True)
ex_cols = st.columns(len(EXAMPLES))
for i, (col, example) in enumerate(zip(ex_cols, EXAMPLES)):
    with col:
        if st.button(example, key=f"ex_{i}"):
            st.session_state.question = example
            st.rerun()

st.divider()

# ── Stage 1: Question → SQL generation ───────────────────────────────────────

active_question = question or st.session_state.question

if run_clicked and active_question.strip():
    logger.info("New question submitted | question=%r", active_question)
    with st.spinner("Generating SQL…"):
        try:
            generated = text_to_sql(active_question)
        except EnvironmentError as e:
            st.error(f"**Setup required:** {e}")
            st.stop()
        except Exception as e:
            logger.error("text_to_sql error | %s", e, exc_info=True)
            st.error(f"Could not generate SQL. OpenAI error: {e}")
            st.stop()
    # Store and rerun so the editor renders cleanly
    st.session_state.generated_sql = generated
    st.session_state.pending_question = active_question
    st.rerun()

elif run_clicked and not active_question.strip():
    st.warning("Please enter a question before clicking Run.")

# ── Stage 2: SQL editor + execute ────────────────────────────────────────────

if st.session_state.generated_sql:
    ai_sql = st.session_state.generated_sql

    st.markdown('<div class="card-title">📝 Generated SQL</div>', unsafe_allow_html=True)

    edited_sql = st.text_area(
        label="sql_editor",
        value=ai_sql,
        height=140,
        label_visibility="collapsed",
        key="sql_editor",
    )

    is_edited = edited_sql.strip() != ai_sql.strip()
    badge_html = (
        '<span class="sql-badge badge-edited">✏️ Edited</span>'
        if is_edited else
        '<span class="sql-badge badge-ai">✨ AI generated</span>'
    )
    run_sql_col, badge_col = st.columns([1, 5])
    with run_sql_col:
        run_sql = st.button("Run SQL ▶", type="primary", use_container_width=True)
    with badge_col:
        st.markdown(
            f"<p style='margin:0.6rem 0 0;font-size:0.82rem;color:#6B7280'>"
            f"Edit the SQL above if needed, then click Run SQL ▶  {badge_html}</p>",
            unsafe_allow_html=True,
        )

    if run_sql:
        sql_to_run = edited_sql.strip()
        exec_question = st.session_state.pending_question

        # ── Execute ───────────────────────────────────────────────────────────
        with st.spinner("Running query…"):
            try:
                df = execute_query(sql_to_run)
            except ValueError as e:
                st.error(f"**Query blocked for safety:** {e}")
                st.stop()
            except Exception as e:
                logger.error("execute_query error | %s", e, exc_info=True)
                st.error(f"**SQL error:** {e}")
                st.stop()

        logger.info(
            "execute | edited=%s | rows=%d | question=%r",
            is_edited, len(df), exec_question,
        )

        # ── Chart ─────────────────────────────────────────────────────────────
        chart_type = pick_chart_type(df)
        fig = render_chart(df, chart_type)

        # ── Insight ───────────────────────────────────────────────────────────
        insight = None
        if not df.empty:
            with st.spinner("Generating insights…"):
                try:
                    insight = generate_insight(exec_question, df)
                except Exception as e:
                    logger.warning("generate_insight error | %s", e)

        # ── Persist to history ────────────────────────────────────────────────
        st.session_state.history.insert(0, {
            "question": exec_question,
            "sql": sql_to_run,
            "insight": insight,
        })
        # Clear so a fresh question starts clean
        st.session_state.generated_sql = None
        st.session_state.pending_question = ""

        # ── Render results ────────────────────────────────────────────────────
        st.divider()

        if df.empty:
            st.info("No data found for this query. Try rephrasing your question.")
        else:
            if chart_type == "metric":
                num_cols = df.select_dtypes(include="number").columns
                col_name = num_cols[0]
                val = df[col_name].iloc[0]
                st.metric(
                    label=col_name.replace("_", " ").title(),
                    value=f"{val:,.2f}" if isinstance(val, float) else f"{val:,}",
                )
            else:
                left, right = st.columns([1, 1], gap="large")
                with left:
                    st.markdown('<div class="card-title">📋 Results</div>', unsafe_allow_html=True)
                    st.dataframe(df, width="stretch", height=320)
                with right:
                    st.markdown('<div class="card-title">📈 Chart</div>', unsafe_allow_html=True)
                    if fig:
                        st.plotly_chart(fig, width="stretch")
                    else:
                        st.info("Chart not available for this result shape.")

            if insight:
                st.markdown("")
                st.markdown('<div class="card-title">💡 AI Insights</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="insight-box">{insight}</div>', unsafe_allow_html=True)
            else:
                st.warning("Insights unavailable (API issue). Table and chart above are still accurate.")

# ── Query history (sidebar) ───────────────────────────────────────────────────

if st.session_state.history:
    with st.sidebar:
        st.markdown("### 🕑 Query History")
        for i, item in enumerate(st.session_state.history[:10]):
            with st.expander(f"{item['question'][:50]}…" if len(item['question']) > 50 else item['question']):
                st.code(item["sql"], language="sql")
                if item.get("insight"):
                    st.markdown(item["insight"])
