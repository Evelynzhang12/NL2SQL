"""Tests for clarification robustness in the NL2SQL pipeline.

Covers the time-window and ticker-matching improvements to needs_clarification:
explicit time windows expressed in natural language should be recognised, and
tickers should only match as whole words (so "meta" does not match "metadata").

These tests exercise pure logic only - no database or LLM access is required.
"""
import os

# needs_clarification imports through src.config, which validates that these env
# vars exist at import time. They are never actually used by the clarify logic.
os.environ.setdefault("DATABASE_URL", "dummy://test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")

from src.core.nl2sql import (  # noqa: E402
    needs_clarification,
    has_explicit_time_window,
    find_mentioned_tickers,
)
from src.core.safety_checks import check_time_window_correct  # noqa: E402


# ---------- has_explicit_time_window ----------

class TestHasExplicitTimeWindow:
    def test_numeric_day_window(self):
        assert has_explicit_time_window("average close over 30 days")

    def test_past_n_weeks(self):
        assert has_explicit_time_window("NVDA trend over the past 2 weeks")

    def test_last_n_months(self):
        assert has_explicit_time_window("performance in the last 3 months")

    def test_this_year(self):
        assert has_explicit_time_window("how did AAPL do this year")

    def test_today_keyword(self):
        assert has_explicit_time_window("NVDA price today")

    def test_vague_recent_has_no_window(self):
        assert not has_explicit_time_window("show me recent prices")

    def test_no_time_reference(self):
        assert not has_explicit_time_window("what is the closing price of AAPL")


# ---------- find_mentioned_tickers ----------

class TestFindMentionedTickers:
    def test_single_ticker(self):
        assert find_mentioned_tickers("what is NVDA doing") == ["nvda"]

    def test_two_tickers(self):
        assert set(find_mentioned_tickers("compare NVDA and AAPL")) == {"nvda", "aapl"}

    def test_meta_not_matched_inside_metadata(self):
        # "meta" must not be found inside the unrelated word "metadata"
        assert "meta" not in find_mentioned_tickers("show the metadata average")

    def test_meta_matched_as_whole_word(self):
        assert "meta" in find_mentioned_tickers("how is META trading")


# ---------- needs_clarification (end-to-end logic) ----------

class TestNeedsClarification:
    def test_explicit_window_does_not_trigger_time_clarify(self):
        # Previously "past 2 weeks" was not in the hardcoded list and wrongly
        # triggered a time_window clarification.
        result = needs_clarification("What is the recent trend for NVDA over the past 2 weeks?")
        missing = result.get("missing_slots", {}) if result.get("needs_clarify") else {}
        assert "time_window" not in missing

    def test_vague_time_still_triggers_clarify(self):
        result = needs_clarification("What was the trend for AAPL recently?")
        assert result["needs_clarify"] is True
        assert "time_window" in result["missing_slots"]

    def test_metadata_does_not_count_as_second_ticker(self):
        # "better"/"than" triggers a comparison check; only NVDA is a real ticker,
        # so the system should ask what to compare against.
        result = needs_clarification("Is NVDA better than the metadata average?")
        assert result["needs_clarify"] is True
        assert "comparison_baseline" in result["missing_slots"]

    def test_unambiguous_question_proceeds(self):
        result = needs_clarification("What is the closing price of AAPL on 2025-01-10?")
        assert result["needs_clarify"] is False


# ---------- check_time_window_correct (safety check) ----------

class TestTimeWindowSafetyCheck:
    def test_metadata_is_not_treated_as_meta_ticker(self):
        # "metadata" must not match the META ticker, so a query without a real
        # ticker should not be failed for lacking MAX("timestamp").
        sql = "SELECT AVG(close) FROM stock_data LIMIT 5;"
        assert check_time_window_correct("show the metadata average recently", sql) is True

    def test_real_ticker_without_max_timestamp_fails(self):
        # A real ticker with a time reference but no MAX("timestamp") anchor
        # should still be flagged as incorrect time windowing.
        sql = "SELECT close FROM stock_data WHERE ticker='NVDA' LIMIT 5;"
        assert check_time_window_correct("NVDA price last week", sql) is False
