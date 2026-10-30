"""Tests for the Groq ASR provider.

The real HTTP request is mocked so the test suite runs offline and does not
require a real Groq API key.
"""

from unittest import mock

import pytest

from app.config import Settings, clear_settings_cache, get_settings
from app import groq_asr


@pytest.fixture(autouse=True)
def reset_settings():
    # Ensure a clean Settings object for each test
    clear_settings_cache()
    yield
    clear_settings_cache()


def test_transcribe_success(monkeypatch):
    # Prepare a dummy Settings with a Groq API key
    class DummySettings:
        groq_api_key: str = "dummy-key"
    monkeypatch.setattr("app.config.get_settings", lambda: DummySettings())

    # Mock the HTTP response from Groq
    fake_response = mock.Mock()
    fake_response.status_code = 200
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {
        "language": "en",
        "duration": 5.0,
        "segments": [
            {"id": "s1", "start": 0.0, "end": 2.5, "text": "hello world", "avg_logprob": -0.1},
            {"id": "s2", "start": 2.5, "end": 5.0, "text": "test", "avg_logprob": -0.2},
        ],
    }
    # The code posts with httpx; patching requests.post left the real Groq API being called.
    monkeypatch.setattr("httpx.post", lambda *args, **kwargs: fake_response)

    transcript = groq_asr.transcribe_file("dummy.wav")
    assert transcript.language == "en"
    assert len(transcript.segments) == 2
    assert transcript.segments[0].text == "hello world"
    assert transcript.segments[1].text == "test"
    # confidence should be exp(-0.1) and exp(-0.2) clamped
    assert transcript.segments[0].confidence == round(max(0.0, min(1.0, __import__("math").exp(-0.1))), 3)


def test_missing_api_key(monkeypatch):
    # Settings without a Groq API key
    class DummySettings:
        groq_api_key: str | None = None
    monkeypatch.setattr("app.config.get_settings", lambda: DummySettings())
    with pytest.raises(RuntimeError, match="Groq API key not configured"):
        groq_asr.transcribe_file("dummy.wav")
