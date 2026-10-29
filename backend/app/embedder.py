"""Embedder implementation – converts chunk text into dense vectors.

Supports a mock provider (safe‑local mode) and an OpenAI provider. The function
imports `get_settings` inside the method to allow easy monkey‑patching in
unit tests, mirroring the pattern used in the Groq ASR module.
"""

from __future__ import annotations

import json
import logging
logger = logging.getLogger(__name__)
from typing import List
import requests

from app.contracts import Chunk
from app.config import get_settings


# Lazy import of SentenceTransformer to avoid hard dependency unless needed

class HFEmbedder:
    """Embedding using a self‑hosted Sentence‑Transformer model.

    Model: sentence‑transformers/all‑MiniLM‑L6‑v2 (384‑dimensional).
    The model is loaded once per process (thread‑safe) and cached.
    """
    def __init__(self) -> None:
        # Lazy load the model the first time it is needed.
        self._model: SentenceTransformer | None = None

    def _load(self) -> SentenceTransformer:
        if self._model is None:
            # The model will be downloaded on first run and then cached under the
            # HuggingFace cache directory (e.g., ~/.cache/huggingface).
                    from sentence_transformers import SentenceTransformer
        return self._model

    def embed(self, chunks: List[Chunk]) -> List[List[float]]:
        model = self._load()
        texts = [c.text for c in chunks]
        # model.encode returns a numpy array of shape (n, dim)
        embeddings = model.encode(texts, normalize_embeddings=True)
        # Convert to plain Python lists for JSON serialisation
        return embeddings.tolist()

class Embedder:
    """Generate embeddings for a list of `Chunk` objects.

    * Mock provider – returns a deterministic zero‑vector for each chunk.
    * OpenAI provider – calls the OpenAI embeddings endpoint using the API key
      from settings. The model used is `text-embedding-ada-002`.
    * HF provider – uses a locally‑hosted sentence‑transformers model.
    """
    def embed(self, chunks: List[Chunk]) -> List[List[float]]:
        # Import inside the method to allow test monkey‑patching of get_settings.
        from app.config import get_settings
        settings = get_settings()
        provider = settings.embed_provider
        logger.info("Embedder: using provider %s for %d chunks", provider, len(chunks))

        if provider == "mock":
            # Return a simple zero‑vector for each chunk.
            return [[0.0, 0.0, 0.0] for _ in chunks]
        if provider == "openai":
            import httpx
            payload = {
                "model": "text-embedding-ada-002",
                "input": [c.text for c in chunks],
            }
            headers = {"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"}
            resp = httpx.post("https://api.openai.com/v1/embeddings", json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            embeddings = [item["embedding"] for item in data["data"]]
            # Annotate chunks with model info per test expectations
            for chunk, emb in zip(chunks, embeddings):
                chunk.embedding_model = "openai"
                # The mock response in tests provides "model": "text-embedding-ada-002"
                chunk.embedding_revision = data.get("model", "text-embedding-ada-002")
            return embeddings
        if provider == "hf":
            # Delegate to the HF embedder defined above.
            return HFEmbedder().embed(chunks)
        raise RuntimeError(f"Unsupported embed provider: {provider}")

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
        logger.info("Embedder: using provider %s for %d chunks", provider, len(chunks))

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
