from types import SimpleNamespace

import pytest

from app.llm import get_chat_model, structured_output_method


def test_ollama_provider_returns_chat_ollama(monkeypatch):
    settings = SimpleNamespace(
        llm_provider="ollama",
        ollama_api_key="secret",
        ollama_base_url="https://ollama.com",
        ollama_model="x",
        groq_api_key=None,
        openai_api_key=None,
    )
    monkeypatch.setattr("app.llm.get_settings", lambda: settings)

    model = get_chat_model()

    assert type(model).__name__ == "ChatOllama"
    assert model.model == "x"
    assert (model.client_kwargs or {}).get("headers", {}).get("Authorization") == "Bearer secret"


def test_ollama_structured_output_method(monkeypatch):
    settings = SimpleNamespace(
        llm_provider="ollama",
        ollama_api_key="secret",
        ollama_base_url="https://ollama.com",
        ollama_model="beam:cloud",
        groq_api_key=None,
        openai_api_key=None,
    )
    monkeypatch.setattr("app.llm.get_settings", lambda: settings)

    assert structured_output_method() == "function_calling"


def test_groq_provider_requires_key(monkeypatch):
    settings = SimpleNamespace(
        llm_provider="groq",
        ollama_api_key=None,
        ollama_base_url="https://ollama.com",
        ollama_model="x",
        groq_api_key=None,
        openai_api_key=None,
    )
    monkeypatch.setattr("app.llm.get_settings", lambda: settings)

    with pytest.raises(RuntimeError):
        get_chat_model()
