"""
AI layer: text-to-SQL and insight generation via OpenAI.
"""

import logging
import os
import re
import time

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

from src.prompts import (
    SYSTEM_INSIGHT,
    SYSTEM_TEXT_TO_SQL,
    user_insight_prompt,
    user_sql_prompt,
)

load_dotenv()

logger = logging.getLogger(__name__)

_client: OpenAI | None = None

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
MAX_ROWS_FOR_INSIGHT = int(os.getenv("MAX_ROWS_FOR_INSIGHT", "50"))

# Retry settings for rate-limit errors
_RETRY_DELAY = 2.0
_MAX_RETRIES = 1


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set. "
                "Copy .env.example to .env and add your key."
            )
        _client = OpenAI(api_key=api_key)
    return _client


def _chat(system: str, user: str, temperature: float = 0.0) -> tuple[str, int]:
    """
    Calls the OpenAI chat completions endpoint with one retry on rate-limit.
    Returns (response_text, total_tokens_used).
    """
    client = _get_client()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=temperature,
            )
            text = response.choices[0].message.content.strip()
            tokens = response.usage.total_tokens if response.usage else 0
            return text, tokens
        except RateLimitError:
            if attempt < _MAX_RETRIES:
                logger.warning("Rate limit hit. Retrying in %.1fs…", _RETRY_DELAY)
                time.sleep(_RETRY_DELAY)
            else:
                raise


def _strip_sql_fences(text: str) -> str:
    """Removes markdown code fences that the LLM sometimes wraps SQL in."""
    text = re.sub(r"^```(?:sql)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


# ── Public API ────────────────────────────────────────────────────────────────

def text_to_sql(question: str) -> str:
    """
    Converts a natural-language question to a SQLite SELECT query.
    Returns the raw SQL string.
    Raises EnvironmentError if the API key is missing.
    Raises openai.APIError / RateLimitError on API failure.
    """
    logger.info("text_to_sql | question=%r", question)

    user_msg = user_sql_prompt(question)
    sql_raw, tokens = _chat(SYSTEM_TEXT_TO_SQL, user_msg, temperature=0.0)
    sql = _strip_sql_fences(sql_raw)

    logger.info("text_to_sql | tokens_used=%d | sql=%s", tokens, sql[:120].replace("\n", " "))
    return sql


def generate_insight(question: str, df: pd.DataFrame) -> str:
    """
    Generates bullet-point insights from query results.
    Caps the DataFrame at MAX_ROWS_FOR_INSIGHT rows before sending to the LLM.
    Returns a markdown-formatted insight string.
    """
    if df.empty:
        return "No data returned — nothing to analyse."

    sample = df.head(MAX_ROWS_FOR_INSIGHT)
    table_md = sample.to_markdown(index=False)

    logger.info(
        "generate_insight | question=%r | rows_sent=%d", question, len(sample)
    )

    user_msg = user_insight_prompt(question, table_md)
    insight, tokens = _chat(SYSTEM_INSIGHT, user_msg, temperature=0.3)

    logger.info("generate_insight | tokens_used=%d", tokens)
    return insight
