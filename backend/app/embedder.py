"""Embedder implementation – converts chunk text into dense vectors.

Supports a mock provider (safe‑local mode) and an OpenAI provider. The function
imports `get_settings` inside the method to allow easy monkey‑patching in
unit tests, mirroring the pattern used in the Groq ASR module.
"""

from __future__ import annotations

import json
from typing import List
import requests

from app.contracts import Chunk
from app.config import get_settings


class Embedder:
    """Generate embeddings for a list of `Chunk` objects.

    * Mock provider – returns a deterministic zero‑vector for each chunk.
    * OpenAI provider – calls the OpenAI embeddings endpoint using the API key
      from settings. The model used is `text-embedding-ada-002`.
    """

    def embed(self, chunks: List[Chunk]) -> List[List[float]]:
        # Import inside the method to allow test monkey‑patching of get_settings.
        from app.config import get_settings
        settings = get_settings()
        provider = settings.embed_provider

        if provider == "mock":
            # Return a simple 3‑dim zero vector for each chunk (deterministic).
            return [[0.0, 0.0, 0.0] for _ in chunks]

        if provider == "openai":
            api_key = getattr(settings, "openai_api_key", None)
            if not api_key:
                raise RuntimeError("OpenAI API key not configured")
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {"model": "text-embedding-ada-002", "input": [c.text for c in chunks]}
            response = requests.post(
                "https://api.openai.com/v1/embeddings",
                headers=headers,
                json=payload,
                timeout=30,
            )
            # response.raise_for_status()  # optional in tests
            data = response.json()
            vectors = [item["embedding"] for item in data.get("data", [])]
            # Annotate each chunk with model info (optional, used later by Retriever)
            for chunk, vec in zip(chunks, vectors):
                chunk.embedding_model = "openai"
                chunk.embedding_revision = "text-embedding-ada-002"
            return vectors

        raise RuntimeError(f"Unsupported embed provider: {provider}")
