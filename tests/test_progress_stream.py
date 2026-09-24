"""The progress stream reports actual work and keeps normal API compatibility."""
import json
import pytest
from fastapi.testclient import TestClient
from src.api.app import app
from src.api import endpoints
from src.core import nl2sql
from src.core.progress import progress_listener, report_stage


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(endpoints, 'insert_audit_log', lambda log: None)
    monkeypatch.setattr(nl2sql, 'generate_sql', lambda *a, **kw: "SELECT AVG(close) AS avg_close FROM stock_data")
    monkeypatch.setattr(nl2sql.SQLValidator, 'validate', lambda *a: {'valid': True, 'issues': []})
    monkeypatch.setattr(nl2sql, 'run_sql', lambda sql: {'columns': ['avg_close'], 'rows': [[164.76]]})
    monkeypatch.setattr(endpoints, 'summarize_answer', lambda question, result: {**result, 'final_answer': 'The average closing price is 164.76.'})
    with TestClient(app) as client:
        yield client


def events(client, question='What is the average closing price of NVDA over 30 days?'):
    response = client.post('/api/v1/query/stream', json={'question': question, 'product_type': 'equities'})
    assert response.status_code == 200
    return [json.loads(line) for line in response.text.splitlines()]


def test_success_reports_real_stages_and_original_response(client):
    result = events(client)
    assert [e['stage'] for e in result if e['type'] == 'stage'] == [
        'clarification', 'product_classification', 'sql_generation', 'safety_validation', 'sql_execution', 'answer_generation']
    assert result[-1]['type'] == 'result'
    assert result[-1]['payload']['status'] == 'ok'
    ordinary = client.post('/api/v1/query', json={'question': 'What is the average close?'})
    assert ordinary.status_code == 200
    assert ordinary.json()['data'] == result[-1]['payload']['data']


def test_clarification_never_emits_execution(client, monkeypatch):
    monkeypatch.setattr(nl2sql, 'needs_clarification', lambda *a, **kw: {'needs_clarify': True, 'missing_slots': {'time_window': 'Which period?'}})
    result = events(client)
    assert [e['stage'] for e in result if e['type'] == 'stage'] == ['clarification']
    assert result[-1]['payload']['status'] == 'clarify'


def test_blocked_query_never_emits_execution(client, monkeypatch):
    monkeypatch.setattr(nl2sql, 'generate_sql', lambda *a, **kw: 'DROP TABLE stock_data')
    result = events(client)
    assert 'sql_execution' not in [e.get('stage') for e in result]
    assert result[-1]['payload']['status'] == 'blocked'


def test_unexpected_error_is_terminal_stream_event(client, monkeypatch):
    monkeypatch.setattr(endpoints, 'eval_one', lambda *a, **kw: 1 / 0)
    result = events(client)
    assert result[-1] == {'type': 'error', 'message': 'Internal server error'}


def test_context_listeners_are_isolated_between_threads():
    from concurrent.futures import ThreadPoolExecutor
    def request(label):
        seen = []
        token = progress_listener.set(seen.append)
        try:
            report_stage(label)
            return seen
        finally:
            progress_listener.reset(token)
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(request, ['first', 'second'])) == [['first'], ['second']]
    assert progress_listener.get() is None


def test_crypto_is_accepted_by_both_endpoints(client):
    payload = {'question': 'Show BTC closing price.', 'product_type': 'crypto'}
    assert client.post('/api/v1/query', json=payload).status_code == 200
    streamed = client.post('/api/v1/query/stream', json=payload)
    assert streamed.status_code == 200
    result = json.loads(streamed.text.splitlines()[-1])
    assert result['payload']['meta']['product_type'] == 'crypto'
