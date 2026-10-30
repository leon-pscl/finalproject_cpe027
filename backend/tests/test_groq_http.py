"""Tests for the shared Groq retry helper. No real HTTP is performed."""

import httpx
import pytest

from app import groq_http


def _resp(status: int, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status, headers=headers or {}, json={"ok": status < 400},
        request=httpx.Request("POST", "https://api.groq.com/x"),
    )


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Keep the tests instant and record how long each retry waited."""
    waits: list[float] = []
    monkeypatch.setattr(groq_http.time, "sleep", waits.append)
    monkeypatch.setattr(groq_http.random, "uniform", lambda a, b: 0.0)
    return waits


def test_returns_first_success(monkeypatch):
    calls = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: calls.append(1) or _resp(200))
    assert groq_http.post_with_retry("https://api.groq.com/x").status_code == 200
    assert len(calls) == 1


def test_retries_429_then_succeeds(monkeypatch, _no_sleep):
    responses = [_resp(429, {"Retry-After": "3"}), _resp(200)]
    monkeypatch.setattr(httpx, "post", lambda *a, **k: responses.pop(0))
    assert groq_http.post_with_retry("https://api.groq.com/x").status_code == 200
    assert _no_sleep == [3.0]  # honoured Retry-After rather than the 2s default backoff


def test_retry_after_with_unit_suffix(monkeypatch, _no_sleep):
    responses = [_resp(429, {"Retry-After": "7.66s"}), _resp(200)]
    monkeypatch.setattr(httpx, "post", lambda *a, **k: responses.pop(0))
    groq_http.post_with_retry("https://api.groq.com/x")
    assert _no_sleep == [7.66]


def test_retry_after_garbage_falls_back_to_backoff(monkeypatch, _no_sleep):
    responses = [_resp(429, {"Retry-After": "soon"}), _resp(200)]
    monkeypatch.setattr(httpx, "post", lambda *a, **k: responses.pop(0))
    groq_http.post_with_retry("https://api.groq.com/x")
    assert _no_sleep == [groq_http.BASE_BACKOFF]


def test_retry_after_is_capped(monkeypatch, _no_sleep):
    responses = [_resp(429, {"Retry-After": "99999"}), _resp(200)]
    monkeypatch.setattr(httpx, "post", lambda *a, **k: responses.pop(0))
    groq_http.post_with_retry("https://api.groq.com/x")
    assert _no_sleep == [groq_http.MAX_BACKOFF]


def test_raises_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _resp(429))
    with pytest.raises(httpx.HTTPStatusError):
        groq_http.post_with_retry("https://api.groq.com/x", max_retries=3)


def test_retries_network_error_then_succeeds(monkeypatch):
    calls = []

    def flaky(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("reset")
        return _resp(200)

    monkeypatch.setattr(httpx, "post", flaky)
    assert groq_http.post_with_retry("https://api.groq.com/x").status_code == 200
    assert len(calls) == 2


def test_network_error_raises_on_last_attempt(monkeypatch):
    def always_fail(*a, **k):
        raise httpx.ConnectError("reset")

    monkeypatch.setattr(httpx, "post", always_fail)
    with pytest.raises(httpx.ConnectError):
        groq_http.post_with_retry("https://api.groq.com/x", max_retries=2)


def test_4xx_is_not_retried(monkeypatch):
    calls = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: calls.append(1) or _resp(401))
    with pytest.raises(httpx.HTTPStatusError):
        groq_http.post_with_retry("https://api.groq.com/x")
    assert len(calls) == 1  # a bad key must fail fast, not sleep through 5 attempts
