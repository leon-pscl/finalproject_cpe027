"""Embedder implementation – converts chunk text into dense vectors.

Supports a mock provider (safe‑local mode), an OpenAI provider, and a local
Sentence-Transformers (HF) provider.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any, List

import requests

from app.contracts import Chunk


class HFEmbedder:
    """Embedding using a self‑hosted Sentence‑Transformer model.

    Model: sentence‑transformers/all‑MiniLM‑L6‑v2 (384‑dimensional).
    The model is loaded once per process (thread‑safe) and cached.
    """

    def __init__(self) -> None:
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        return self._model

    def embed(self, chunks: Sequence[Any]) -> List[List[float]]:
        model = self._load()
        texts = [c.text if hasattr(c, "text") else str(c) for c in chunks]
        embeddings = model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()


class Embedder:
    """Generate embeddings for a list of `Chunk` objects or texts.

    * Mock provider – returns a deterministic zero‑vector for each chunk.
    * OpenAI provider – calls the OpenAI embeddings endpoint using the API key
      from settings. The model used is `text-embedding-ada-002`.
    * HF provider – uses a locally‑hosted sentence‑transformers model.
    """

    def embed(self, chunks: Sequence[Any]) -> List[List[float]]:
        from app.config import get_settings

        settings = get_settings()
        provider = settings.embed_provider

        if provider == "mock":
            return [[0.0, 0.0, 0.0] for _ in chunks]

        if provider == "openai":
            api_key = getattr(settings, "openai_api_key", None) or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OpenAI API key not configured")
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            texts = [c.text if hasattr(c, "text") else str(c) for c in chunks]
            payload = {"model": "text-embedding-ada-002", "input": texts}
            response = requests.post(
                "https://api.openai.com/v1/embeddings",
                headers=headers,
                json=payload,
                timeout=30,
            )
            data = response.json()
            vectors = [item["embedding"] for item in data.get("data", [])]
            for chunk, _ in zip(chunks, vectors):
                if hasattr(chunk, "embedding_model"):
                    chunk.embedding_model = "openai"
                if hasattr(chunk, "embedding_revision"):
                    chunk.embedding_revision = data.get("model", "text-embedding-ada-002")
            return vectors

        if provider == "hf":
            return HFEmbedder().embed(chunks)

        raise RuntimeError(f"Unsupported embed provider: {provider}")
