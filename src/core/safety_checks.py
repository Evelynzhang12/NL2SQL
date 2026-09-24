"""SQL safety validation and security checks"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from src.constants import SUPPORTED_TICKERS, TIME_INDICATORS
from src.core.sql_guard import is_read_only, uses_only_allowed_tables
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ==================== Individual Check Functions ====================


def check_select_only(sql: str) -> bool:
    """
    Verify that SQL is a single read-only (SELECT) query.

    Uses AST-based parsing so string literals or identifiers that merely
    contain SQL keywords are not misclassified.

    Args:
        sql: SQL query to check

    Returns:
        True if query is a single read-only statement
    """
    if not sql:
        return False
    return is_read_only(sql)


def check_no_table_modification(sql: str) -> bool:
    """
    Verify that SQL does not modify, create, or drop tables.

    A read-only SELECT statement cannot modify tables, so this reuses the
    structural read-only check rather than substring keyword matching (which
    would false-positive on e.g. a column named "deleted_at").

    Args:
        sql: SQL query to check

    Returns:
        True if query does not modify tables
    """
    if not sql:
        return False
    return is_read_only(sql)


def check_source_correct(sql: str) -> bool:
    """
    Verify that SQL only accesses allowed tables.

    Uses AST-based table extraction (CTE names excluded) so subqueries and
    common table expressions are handled correctly.

    Args:
        sql: SQL query to check

    Returns:
        True if query only uses allowed tables
    """
    if not sql:
        return False
    return uses_only_allowed_tables(sql)


def check_time_window_correct(question: str, sql: str) -> bool:
    """
    Verify that time window handling is correct.
    
    Rules:
    1. If question mentions time-related keywords, SQL should not use NOW()
    2. If question mentions ticker names, the query should be bounded on the
       "date" column -- either anchored on MAX("date") or filtered against
       explicit date literals. Both are correct ways to scope a time window.
    
    Args:
        question: Original question
        sql: Generated SQL
        
    Returns:
        True if time window is correct
    """
    if not sql:
        return False
    
    q = question.lower()
    s = sql.lower()
    
    # Check if question uses time keywords
    needs_time_rule = any(k in q for k in TIME_INDICATORS)
    
    if not needs_time_rule:
        return True
    
    # Historical data should not use NOW()
    if "now(" in s:
        return False
    
    # If specific ticker is mentioned, the query must scope a time window.
    # Match tickers as whole words so "meta" is not found inside e.g. "metadata".
    mentioned_tickers = [
        t.upper() for t in SUPPORTED_TICKERS if re.search(rf"\b{re.escape(t)}\b", q)
    ]
    
    if mentioned_tickers:
        return _has_date_window(s)
    
    return True


def _has_date_window(sql_lower: str) -> bool:
    """
    Check whether SQL scopes a time window on the "date" column.
    
    Two shapes are accepted, both correct:
    - Anchored:  MAX("date") used as a reference point, e.g.
                 WHERE "date" >= (SELECT max_ts FROM anchor) - INTERVAL '10 days'
    - Absolute:  "date" compared against a literal, e.g.
                 WHERE "date" >= '2025-07-01'
    
    Args:
        sql_lower: Lowercased SQL
        
    Returns:
        True if a date-based time window is present
    """
    # Anchored form: MAX("date") / MAX(date)
    if re.search(r'max\(\s*"?date"?\s*\)', sql_lower):
        return True
    
    # Absolute form: "date" compared with <, <=, >, >=, or BETWEEN
    if re.search(r'"?\bdate\b"?\s*(>=|<=|>|<|between)', sql_lower):
        return True
    
    return False


def check_permission_granted(exec_status: str, error_message: str = "") -> bool:
    """
    Verify that backend has database execution permissions.
    
    Args:
        exec_status: Query execution status
        error_message: Error message if any
        
    Returns:
        True unless permission-related error occurred
    """
    # These statuses indicate successful execution or non-permission errors
    if exec_status in {"ok", "no_data", "clarify"}:
        return True
    
    # Check for permission-related errors
    msg = (error_message or "").lower()
    permission_markers = ["permission denied", "not authorized", "insufficient privilege"]
    if any(m in msg for m in permission_markers):
        return False
    
    # Other errors default to True (may be SQL logic errors, not permission issues)
    return True


def check_connection_stable(exec_status: str, error_message: str = "") -> bool:
    """
    Verify that database connection is stable.
    
    Args:
        exec_status: Query execution status
        error_message: Error message if any
        
    Returns:
        False if connection-related error occurred, True otherwise
    """
    if exec_status != "error":
        return True
    
    # Check for connection-related errors
    msg = (error_message or "").lower()
    connection_markers = [
        "connection",
        "ssl",
        "pool",
        "timeout",
        "closed",
        "disconnected",
    ]
    
    return not any(marker in msg for marker in connection_markers)


# ==================== Comprehensive Safety Check ====================


def build_safety_checks(
    question: str,
    sql: Optional[str],
    status: str,
    message: str = "",
) -> Dict[str, Any]:
    """
    Build comprehensive three-stage safety checks.
    
    Stages:
    1. sql_generation: Verify SQL is safe to generate
    2. safety_validation: Verify business rules are followed
    3. execution: Verify execution state
    
    Args:
        question: Original question
        sql: Generated SQL (may be None for clarify/error)
        status: Query execution status
        message: Error message if any
        
    Returns:
        Dict with three safety check stages
    """
    logger.debug("Building safety checks...")
    
    return {
        "sql_generation": {
            "select_only": check_select_only(sql) if sql else False,
            "no_table_modification": check_no_table_modification(sql) if sql else False,
            "source_correct": check_source_correct(sql) if sql else False,
        },
        "safety_validation": {
            "time_window_correct": check_time_window_correct(question, sql) if sql else False,
        },
        "execution": {
            "permission_granted": check_permission_granted(status, message),
            "connection_stable": check_connection_stable(status, message),
        },
    }
