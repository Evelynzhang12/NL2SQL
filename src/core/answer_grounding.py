"""Answer grounding validation for NL2SQL responses."""

import re

from typing import Any, Dict, List


def _claim_text(answer: str) -> str:
    """Remove explicit evidence disclaimers, preserving any adjacent claims.

    This remains a conservative rule-based check, not semantic verification.
    Match only the disclaimer phrase, never discard an entire sentence merely
    because it contains a negation.
    """
    metric = r"(?:volatility|stability|trends?|causality)"
    metrics = rf"{metric}(?:\s*(?:,|or|and)\s*{metric})*"
    patterns = [
        rf"\bno (?:additional )?(?:information|context|evidence)(?: or (?:information|context|evidence))? (?:is|are) available (?:on|about|regarding) {metrics}",
        rf"\b(?:the )?(?:returned |provided |available )?(?:data|results?) (?:does|do) not (?:include|provide|contain|offer) (?:any )?(?:additional )?(?:information|context|evidence|insights?) (?:on|about|regarding) (?:price )?{metrics}",
        rf"\bno (?:additional )?(?:information|conclusions?|claims?) (?:on|about|regarding) {metrics} (?:is|are|can be) (?:supported|drawn|inferred)(?: (?:by|from) (?:the )?(?:returned |provided |available )?(?:data|results?))?",
        rf"\b(?:the (?:returned |provided |available )?(?:data|results?) (?:does|do) not|(?:we|i) cannot) (?:support|indicate|infer|assess|determine|establish) (?:any )?{metrics}",
        rf"\b{metrics} (?:cannot|can not) be (?:inferred|determined|assessed|established)(?: from (?:the )?(?:returned |provided |available )?(?:data|results?))?",
        r"\b(?:there (?:is|are) )?no (?:observable |discernible )?trends?(?: over time| or patterns)?\b",
    ]
    for pattern in patterns:
        answer = re.sub(pattern, "", answer, flags=re.IGNORECASE)
    return answer


def validate_answer_grounding(sql: str, data: Dict[str, Any], final_answer: str) -> Dict[str, Any]:
    """
    Validate whether the final natural-language answer is grounded in the SQL result.
    """
    sql_lower = (sql or "").lower()
    answer_lower = _claim_text((final_answer or "").lower())
    columns = [str(c).lower() for c in data.get("columns", [])]
    rows = data.get("rows", [])

    issues: List[str] = []

    has_single_aggregate = (
        len(rows) == 1
        and len(columns) == 1
        and any(fn in sql_lower for fn in ["avg(", "sum(", "count(", "max(", "min("])
    )

    has_time_series = any(c in columns for c in ["timestamp", "date", "month"])
    # Recognize returned metric aliases such as avg_implied_volatility_pct
    # and avg_iv. A price return alone is not a volatility measurement.
    has_volatility_metric = bool(rows) and any(
        re.search(r"(?:^|_)(?:volatility|iv|stddev|variance)(?:_|$)", c)
        or c == "range"
        for c in columns
    )

    mentions_trend = any(
        word in answer_lower
        for word in ["trend", "trending", "increasing", "decreasing", "stable", "upward", "downward"]
    )

    mentions_volatility = any(
        word in answer_lower
        for word in ["volatility", "volatile", "variance", "standard deviation"]
    )

    mentions_causality = any(
        phrase in answer_lower
        for phrase in ["because", "due to", "driven by", "caused by", "as a result of"]
    )

    if has_single_aggregate and mentions_trend:
        issues.append("Answer mentions trend or stability based on a single aggregate value.")

    if mentions_trend and not has_time_series and has_single_aggregate:
        issues.append("Answer infers trend without time-series output.")

    if mentions_volatility and not has_volatility_metric:
        issues.append("Answer mentions volatility without a volatility-related SQL result.")

    if mentions_causality:
        issues.append("Answer includes causal language that may not be supported by SQL results.")

    return {
        "answer_grounded": len(issues) == 0,
        "unsupported_claims": issues,
    }
