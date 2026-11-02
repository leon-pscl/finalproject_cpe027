"""Factory for the chat model used by notes/answer generation."""

from __future__ import annotations

from typing import Any

from .config import get_settings


def get_chat_model(*, temperature: float = 0.0) -> Any:
    """Return a LangChain chat model for the configured ``llm_provider``."""
    settings = get_settings()
    provider = (settings.llm_provider or "groq").strip().lower()

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        headers = None
        if settings.ollama_api_key:
            headers = {"Authorization": f"Bearer {settings.ollama_api_key}"}
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            client_kwargs={"headers": headers} if headers else {},
            temperature=temperature,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=temperature,
        )

    from langchain_groq import ChatGroq

    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")
    return ChatGroq(
        api_key=settings.groq_api_key,
        model="openai/gpt-oss-20b",
        temperature=temperature,
    )


def structured_output_method() -> str | None:
    """Choose a structured-output mode compatible with the active provider."""
    provider = (get_settings().llm_provider or "groq").strip().lower()
    if provider == "ollama":
        return "function_calling"
    return None
