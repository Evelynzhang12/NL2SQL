"""Regression tests for evidence disclaimers being mistaken for claims."""
import pytest
from src.core.answer_grounding import validate_answer_grounding


def check(answer):
    return validate_answer_grounding("SELECT AVG(close) FROM stock_data", {"columns": ["avg"], "rows": [[100.0]]}, answer)


@pytest.mark.parametrize("answer", [
    "The average is 100. No additional information on volatility or stability is supported by the returned data.",
    "The data does not support volatility. The average is 100.",
    "The data does not indicate volatility or stability levels.",
    "No additional information or context is available regarding trends or volatility.",
    "The data does not include any additional context regarding price stability or volatility.",
    "The returned data does not provide evidence about volatility.",
    "There are no observable trends or patterns beyond the average prices provided, and the data does not indicate volatility or stability levels.",
    "Volatility cannot be inferred from the returned data.",
    "There is no observable trend over time. The average is 100.",
    "There are no observable trends or patterns as the data only contains a single aggregated value.",
])
def test_explicit_disclaimers_do_not_fail(answer):
    assert check(answer)["answer_grounded"] is True


@pytest.mark.parametrize("answer", [
    "Volatility is high.",
    "The price is trending upward.",
    "The price is stable.",
    "The price increased because of earnings.",
    "No additional information on volatility is supported by the data, but volatility is high.",
    "Volatility cannot be inferred from the data. However, the price is stable.",
    "Volatility is not low.",
    "No information is available regarding volatility, but volatility is high.",
    "The data does not include context regarding volatility, but volatility is high.",
    "The data does not indicate volatility, but volatility is high.",
])
def test_unsupported_claims_still_fail(answer):
    assert check(answer)["answer_grounded"] is False
