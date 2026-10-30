"""Embedder implementation – converts chunk text into dense vectors.

Supports a mock provider (safe‑local mode), an OpenAI provider, a Groq provider, and an HF provider.
"""

from __future__ import annotations

import logging
from typing import List

import requests

from app.contracts import Chunk

logger = logging.getLogger(__name__)

from .config import get_settings
class HFEmbedder:
    """Embedding using a self‑hosted Sentence‑Transformer model.

    Model: sentence‑transformers/all‑MiniLM‑L6‑v2 (384‑dimensional).
    The model is loaded once per process (thread‑safe) and cached.
    """
    def __init__(self) -> None:
        # Lazy load the model the first time it is needed.
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            # Load the MiniLM model (cached after first download).
            self._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        return self._model

    def embed(self, chunks: List[Chunk]) -> List[List[float]]:
        model = self._load()
        texts = [c.text for c in chunks]
        embeddings = model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

class Embedder:
    """Generate embeddings for a list of `Chunk` objects.

    * Mock provider – returns a deterministic zero‑vector for each chunk.
    * OpenAI provider – calls the OpenAI embeddings endpoint using the API key
      from settings. The model used is `text-embedding-ada-002`.
    * HF provider – uses a locally‑hosted sentence‑transformers model.
    """
    def embed(self, chunks: List[Chunk]) -> List[List[float]]:
        settings = get_settings()
        provider = settings.embed_provider
        texts = [c.text for c in chunks]
        if provider == "mock":
            # Return deterministic zero‑vectors (3‑dimensional for test expectations)
            vectors = [[0.0, 0.0, 0.0] for _ in chunks]
            for chunk, vec in zip(chunks, vectors):
                chunk.embedding_model = "mock"
                chunk.embedding_revision = "zero"
            return vectors
        if provider in ("openai", "groq"):
            api_key = settings.openai_api_key if provider == "openai" else settings.groq_api_key
            if not api_key:
                raise RuntimeError("OpenAI API key not configured")
            endpoint = "https://api.openai.com/v1/embeddings" if provider == "openai" else "https://api.groq.com/openai/v1/embeddings"
            payload = {"model": "text-embedding-ada-002", "input": texts}
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            embeddings = [item["embedding"] for item in data.get("data", [])]
            for chunk, vec in zip(chunks, embeddings):
                chunk.embedding_model = provider
                chunk.embedding_revision = "text-embedding-ada-002"
            return embeddings
        # Default: HF embedder
        vectors = HFEmbedder().embed(chunks)
        for chunk, vec in zip(chunks, vectors):
            chunk.embedding_model = "hf"
            chunk.embedding_revision = "sentence-transformers/all-MiniLM-L6-v2"
        return vectors
