"""
Tests for src/ai.py

All OpenAI API calls are mocked — no real API key required.
Run:  pytest tests/test_ai.py -v
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

import src.ai as ai_module
from src.ai import _strip_sql_fences, generate_insight, text_to_sql


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_openai_response(content: str, total_tokens: int = 100):
    """Builds a minimal mock that mirrors openai.ChatCompletion response structure."""
    choice = SimpleNamespace(message=SimpleNamespace(content=content))
    usage  = SimpleNamespace(total_tokens=total_tokens)
    return SimpleNamespace(choices=[choice], usage=usage)


def _patch_chat(content: str, tokens: int = 100):
    """Context manager: patches openai.chat.completions.create to return content."""
    mock_resp = _make_openai_response(content, tokens)
    return patch.object(
        ai_module._get_client(),           # patches the singleton client
        "__class__",                       # we patch via the module-level _chat helper
    )


# Simpler approach: patch the internal _chat function directly
def _patch_internal_chat(content: str, tokens: int = 100):
    return patch("src.ai._chat", return_value=(content, tokens))


# ── _strip_sql_fences ─────────────────────────────────────────────────────────

class TestStripSQLFences:
    @pytest.mark.parametrize("raw, expected", [
        # No fences — returned as-is
        ("SELECT 1", "SELECT 1"),
        # Standard sql fence
        ("```sql\nSELECT 1\n```", "SELECT 1"),
        # Generic fence (no language tag)
        ("```\nSELECT 1\n```", "SELECT 1"),
        # Uppercase SQL tag
        ("```SQL\nSELECT 1\n```", "SELECT 1"),
        # Extra whitespace inside fences
        ("```sql\n  SELECT *\nFROM customers\n```", "SELECT *\nFROM customers"),
        # Trailing newline after closing fence
        ("```sql\nSELECT 1\n```\n", "SELECT 1"),
    ])
    def test_strips_correctly(self, raw, expected):
        assert _strip_sql_fences(raw) == expected


# ── text_to_sql ───────────────────────────────────────────────────────────────

class TestTextToSQL:
    def test_returns_string(self):
        sql = "SELECT * FROM customers LIMIT 5"
        with _patch_internal_chat(sql):
            result = text_to_sql("Show me 5 customers")
        assert isinstance(result, str)

    def test_returns_stripped_sql(self):
        raw = "```sql\nSELECT * FROM customers LIMIT 5\n```"
        with _patch_internal_chat(raw):
            result = text_to_sql("Show me 5 customers")
        assert result == "SELECT * FROM customers LIMIT 5"

    def test_whitespace_trimmed(self):
        with _patch_internal_chat("  SELECT 1  "):
            result = text_to_sql("anything")
        assert result == "SELECT 1"

    def test_empty_question_still_calls_llm(self):
        with _patch_internal_chat("SELECT 1") as mock_chat:
            text_to_sql("")
            mock_chat.assert_called_once()

    def test_raises_environment_error_without_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # Reset the cached client so it re-reads the env var
        ai_module._client = None
        with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
            text_to_sql("some question")

    def test_multiline_sql_preserved(self):
        multiline = "SELECT c.name,\n       SUM(oi.quantity) AS total\nFROM customers c\nLIMIT 5"
        with _patch_internal_chat(multiline):
            result = text_to_sql("Top customers by quantity")
        assert "SUM" in result
        assert "FROM" in result


# ── generate_insight ──────────────────────────────────────────────────────────

class TestGenerateInsight:
    def _sample_df(self):
        return pd.DataFrame({
            "name":    ["Alice", "Bob", "Carol"],
            "revenue": [48551.35, 41907.63, 39959.03],
        })

    def test_returns_string(self):
        with _patch_internal_chat("• Revenue is high\n• Alice leads"):
            result = generate_insight("Top customers", self._sample_df())
        assert isinstance(result, str)

    def test_returns_insight_content(self):
        insight_text = "• Alice contributes 35% of total revenue."
        with _patch_internal_chat(insight_text):
            result = generate_insight("Top customers", self._sample_df())
        assert result == insight_text

    def test_empty_dataframe_returns_no_data_message(self):
        """Should short-circuit without calling the LLM."""
        with _patch_internal_chat("should not be called") as mock_chat:
            result = generate_insight("Top customers", pd.DataFrame())
        assert "No data" in result
        mock_chat.assert_not_called()

    def test_caps_rows_sent_to_llm(self, monkeypatch):
        """DataFrame with > MAX_ROWS_FOR_INSIGHT rows should be truncated."""
        monkeypatch.setattr(ai_module, "MAX_ROWS_FOR_INSIGHT", 5)
        big_df = pd.DataFrame({
            "name":    [f"Customer{i}" for i in range(100)],
            "revenue": [float(i) for i in range(100)],
        })
        captured_args = {}

        def fake_chat(system, user, temperature=0.0):
            captured_args["user"] = user
            return "• insight", 50

        with patch("src.ai._chat", side_effect=fake_chat):
            generate_insight("test", big_df)

        # The markdown table in the user prompt should have only 5 data rows
        # Each row is a markdown table line starting with |
        data_rows = [
            line for line in captured_args["user"].splitlines()
            if line.startswith("|") and "---" not in line and "name" not in line
        ]
        assert len(data_rows) == 5

    def test_llm_called_with_question_in_prompt(self):
        captured = {}

        def fake_chat(system, user, temperature=0.0):
            captured["user"] = user
            return "• test insight", 50

        question = "What is the revenue breakdown?"
        with patch("src.ai._chat", side_effect=fake_chat):
            generate_insight(question, self._sample_df())

        assert question in captured["user"]


# ── Rate-limit retry ──────────────────────────────────────────────────────────

class TestRateLimitRetry:
    def test_retries_once_on_rate_limit(self):
        """_chat should retry once then succeed."""
        from openai import RateLimitError

        call_count = {"n": 0}

        def mock_create(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RateLimitError(
                    message="rate limit",
                    response=MagicMock(status_code=429, headers={}),
                    body={},
                )
            return _make_openai_response("SELECT 1")

        # Patch the OpenAI client used inside _chat
        ai_module._client = None  # reset singleton
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
            with patch("openai.resources.chat.completions.Completions.create", side_effect=mock_create):
                with patch("src.ai.time.sleep"):  # skip the 2s delay
                    result, _ = ai_module._chat("system", "user")

        assert result == "SELECT 1"
        assert call_count["n"] == 2  # failed once, succeeded on retry
