"""Tests for the Embedder implementation.

We cover both the mock provider and the OpenAI provider (the latter is mocked
via `requests.post`).
"""

from __future__ import annotations

import json
from typing import List

import pytest

from app.embedder import Embedder
from app.contracts import Chunk
from app.config import Settings, get_settings, clear_settings_cache


@pytest.fixture(autouse=True)
def reset():
    clear_settings_cache()
    yield
    clear_settings_cache()


def make_chunks(texts: List[str]) -> List[Chunk]:
    return [
        Chunk(
            chunk_id=f"c{i}",
            lecture_id="demo",
            version="v1",
            segment_ids=[],
            start_s=0.0,
            end_s=0.0,
            text=t,
            embedding_model="",
            embedding_revision="",
        )
        for i, t in enumerate(texts)
    ]


def test_mock_embedder(monkeypatch):
    settings = type("Dummy", (), {"embed_provider": "mock", "openai_api_key": None})()
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    embedder = Embedder()
    chunks = make_chunks(["a", "b"])
    vectors = embedder.embed(chunks)
    assert vectors == [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]


def test_openai_embedder(monkeypatch):
    settings = type("Dummy", (), {"embed_provider": "openai", "openai_api_key": "dummy-key"})()
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    # Mock the HTTP request
    fake_response = type("Resp", (), {"status_code": 200, "json": lambda self: {"data": [{"embedding": [0.1, 0.2, 0.3]}, {"embedding": [0.4, 0.5, 0.6]}], "model": "text-embedding-ada-002"}})()
    monkeypatch.setattr("requests.post", lambda *args, **kwargs: fake_response)
    embedder = Embedder()
    chunks = make_chunks(["first", "second"])
    vectors = embedder.embed(chunks)
    assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    # Verify that the chunks were annotated with model info
    assert all(c.embedding_model == "openai" for c in chunks)
    assert all(c.embedding_revision == "text-embedding-ada-002" for c in chunks)


def test_missing_api_key(monkeypatch):
    settings = type("Dummy", (), {"embed_provider": "openai", "openai_api_key": None})()
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    embedder = Embedder()
    with pytest.raises(RuntimeError, match="OpenAI API key not configured"):
        embedder.embed(make_chunks(["test"]))
