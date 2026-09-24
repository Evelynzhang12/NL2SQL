import pytest
from src.core.answer_grounding import validate_answer_grounding


@pytest.mark.parametrize('column', ['implied_volatility', 'avg_iv', 'avg_implied_volatility_pct', 'daily_return_volatility', 'stddev_samp'])
def test_returned_volatility_metric_aliases_are_recognized(column):
    result = validate_answer_grounding('SELECT metric FROM options_data', {'columns': [column], 'rows': [[0.3]]}, 'The volatility is 0.3.')
    assert result['answer_grounded']


@pytest.mark.parametrize('column', ['return', 'cumulative_return_pct', 'close', 'dividend'])
def test_price_returns_are_not_volatility_evidence(column):
    result = validate_answer_grounding('SELECT metric FROM stock_data', {'columns': [column], 'rows': [[0.3]]}, 'The volatility is 0.3.')
    assert not result['answer_grounded']
