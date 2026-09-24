"""Tests for AST-based SQL safety (src/core/sql_guard.py).

Verifies that structural parsing correctly allows read-only queries over the
allowed tables and rejects everything else - including the cases where the old
substring checks were wrong (string literals / identifiers containing keywords).

Pure parsing logic; no database or LLM access required.
"""
import os

os.environ.setdefault("DATABASE_URL", "dummy://test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")

import pytest  # noqa: E402

from src.core.sql_guard import (  # noqa: E402
    guard_sql,
    is_read_only,
    uses_only_allowed_tables,
)
from src.exceptions import SQLGenerationError, SQLSafetyBlockedError  # noqa: E402


# ---------- queries that must be ALLOWED ----------

class TestAllowed:
    def test_simple_select(self):
        assert guard_sql("SELECT close FROM stock_data LIMIT 5") is not None

    def test_aggregate_select(self):
        assert guard_sql("SELECT AVG(close) FROM stock_data WHERE ticker='NVDA'")

    def test_cte_query(self):
        # CTE name "t" must not be treated as a disallowed table.
        sql = "WITH t AS (SELECT * FROM stock_data) SELECT * FROM t"
        assert guard_sql(sql)

    def test_subquery_same_table(self):
        sql = (
            "SELECT close FROM stock_data WHERE \"timestamp\" >= "
            "(SELECT MAX(\"timestamp\")-'7 days'::interval FROM stock_data)"
        )
        assert guard_sql(sql)

    def test_string_literal_containing_keyword_is_allowed(self):
        # The old substring check rejected this (it contains "drop "), but it is
        # a perfectly safe read-only query - the keyword is inside a string.
        sql = "SELECT close FROM stock_data WHERE ticker = 'DROP TABLE'"
        assert guard_sql(sql)

    def test_column_named_like_keyword_is_allowed(self):
        assert is_read_only("SELECT deleted_at FROM stock_data LIMIT 5")


# ---------- queries that must be REJECTED ----------

class TestRejected:
    @pytest.mark.parametrize("sql", [
        "DROP TABLE stock_data",
        "DELETE FROM stock_data WHERE ticker='NVDA'",
        "UPDATE stock_data SET close=0",
        "INSERT INTO stock_data VALUES (1)",
        "TRUNCATE TABLE stock_data",
        "GRANT SELECT ON stock_data TO bob",
    ])
    def test_non_select_statements_rejected(self, sql):
        with pytest.raises(SQLSafetyBlockedError):
            guard_sql(sql)

    def test_multiple_statements_rejected(self):
        with pytest.raises(SQLGenerationError):
            guard_sql("SELECT close FROM stock_data; DROP TABLE stock_data")

    def test_disallowed_table_rejected(self):
        with pytest.raises(SQLSafetyBlockedError):
            guard_sql("SELECT * FROM users JOIN stock_data USING (id)")

    def test_unparseable_sql_rejected(self):
        with pytest.raises(SQLGenerationError):
            guard_sql("this is not sql !!!")


# ---------- boolean helpers (used by the safety report card) ----------

class TestBooleanHelpers:
    def test_is_read_only_true_for_select(self):
        assert is_read_only("SELECT 1 FROM stock_data") is True

    def test_is_read_only_false_for_delete(self):
        assert is_read_only("DELETE FROM stock_data") is False

    def test_uses_only_allowed_tables_true(self):
        assert uses_only_allowed_tables("SELECT * FROM stock_data") is True

    def test_uses_only_allowed_tables_false(self):
        assert uses_only_allowed_tables("SELECT * FROM users") is False

    def test_uses_only_allowed_tables_ignores_cte_names(self):
        sql = "WITH t AS (SELECT * FROM stock_data) SELECT * FROM t"
        assert uses_only_allowed_tables(sql) is True
