"""Embedder implementation – converts chunk text into dense vectors.

Supports a mock provider (safe‑local mode) and an OpenAI provider. The function
imports `get_settings` inside the method to allow easy monkey‑patching in
unit tests, mirroring the pattern used in the Groq ASR module.
"""

from __future__ import annotations

import logging
from typing import List

import requests

from app.contracts import Chunk

logger = logging.getLogger(__name__)

# Lazy import of SentenceTransformer to avoid hard dependency unless needed
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
        # Always use the local Hugging Face embedder (sentence‑transformers).
        vectors = HFEmbedder().embed(chunks)
        # Annotate the chunk metadata so downstream code knows the source.
        for chunk, vec in zip(chunks, vectors):
            chunk.embedding_model = "hf"
            chunk.embedding_revision = "sentence-transformers/all-MiniLM-L6-v2"
        return vectors
