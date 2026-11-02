import os
import math
import json
from typing import List, Tuple, Any

try:
    import faiss  # type: ignore
except Exception:
    faiss = None  # type: ignore

try:
    from langchain_community.vectorstores import FAISS as LCFaiss  # type: ignore
except Exception:
    LCFaiss = None  # type: ignore

from langchain_core.embeddings import Embeddings  # type: ignore


class _DummyEmbeddings(Embeddings):
    """Minimal embedding adapter used only to satisfy LangChain's load API."""

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [[0.0] * self.dim for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        return [0.0] * self.dim


class FAISSVectorStore:
    """Per-lecture vector index.

    Uses LangChain's FAISS wrapper when available; otherwise keeps a simple in-memory
    metadata fallback so the rest of the app remains usable without FAISS.
    """

    def __init__(self, storage_root: str, lecture_id: str, dim: int = 384) -> None:
        self.dim = dim
        self.base_path = os.path.join(storage_root, "vectors", lecture_id)
        os.makedirs(self.base_path, exist_ok=True)
        self._store = None
        self.metadata: dict[str, Any] = {}
        self.index = None

        if faiss is not None and LCFaiss is not None:
            self._load_or_create()

    def _refresh_metadata(self) -> None:
        self.metadata = {}
        store = self._store
        if store is None or getattr(store, "index", None) is None:
            return
        for i in range(store.index.ntotal):
            doc_id = store.index_to_docstore_id[i]
            doc = store.docstore.search(doc_id)
            chunk = getattr(doc, "metadata", None)
            if not isinstance(chunk, dict) or not chunk:
                page_content = getattr(doc, "page_content", "")
                chunk = {"text": page_content}
            self.metadata[str(i)] = chunk

    def _load_or_create(self) -> None:
        index_file = os.path.join(self.base_path, "index.faiss")
        pkl_file = os.path.join(self.base_path, "index.pkl")
        if LCFaiss is None or not os.path.exists(index_file) or not os.path.exists(pkl_file):
            return
        self._store = LCFaiss.load_local(
            self.base_path,
            _DummyEmbeddings(self.dim),
            allow_dangerous_deserialization=True,
        )
        self.index = self._store.index
        self._refresh_metadata()

    def _persist(self) -> None:
        # LangChain persists in add(); kept for callers that expect the method.
        store = self._store
        if store is not None:
            store.save_local(self.base_path)

    def add(self, chunks: List[Any], vectors: List[List[float]]) -> None:
        if not chunks or not vectors:
            return

        if faiss is None or LCFaiss is None:
            # Minimal no-FAISS fallback: metadata only.
            start_id = len(self.metadata)
            for i, chunk in enumerate(chunks):
                self.metadata[str(start_id + i)] = chunk if isinstance(chunk, dict) else {"text": str(chunk)}
            return

        texts = []
        metadatas = []
        for chunk in chunks:
            data = chunk if isinstance(chunk, dict) else {"text": str(chunk)}
            meta = dict(data)
            texts.append(str(meta.get("text", "")))
            metadatas.append(meta)

        new_store = LCFaiss.from_embeddings(
            list(zip(texts, vectors)),
            _DummyEmbeddings(self.dim),
            metadatas=metadatas,
        )
        if self._store is None:
            self._store = new_store
        else:
            self._store.merge_from(new_store)
        self.index = self._store.index
        self._refresh_metadata()
        self._store.save_local(self.base_path)

    def query(self, query_vec: List[float], top_k: int = 5) -> List[Tuple[Any, float]]:
        if self._store is not None and self.index is not None:
            docs_and_scores = self._store.similarity_search_with_score_by_vector(
                list(query_vec), k=top_k
            )
            results: List[Tuple[Any, float]] = []
            for doc, score in docs_and_scores:
                chunk = getattr(doc, "metadata", None)
                if not isinstance(chunk, dict) or not chunk:
                    chunk = {"text": getattr(doc, "page_content", "")}
                similarity = 1.0 / (1.0 + float(score))
                results.append((chunk, similarity))
            return results

        if not self.metadata:
            return []

        results: List[Tuple[Any, float]] = []
        for _key, chunk in self.metadata.items():
            vec = chunk.get("embedding") if isinstance(chunk, dict) else None
            if not isinstance(vec, list):
                continue
            dot = sum(q * v for q, v in zip(query_vec, vec))
            norm_q = math.sqrt(sum(q * q for q in query_vec))
            norm_v = math.sqrt(sum(v * v for v in vec))
            sim = dot / (norm_q * norm_v) if norm_q and norm_v else 0.0
            results.append((chunk, sim))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def all_chunks(self) -> List[Any]:
        if self.metadata:
            return list(self.metadata.values())
        if self._store is not None and hasattr(self._store, "docstore"):
            chunks: List[Any] = []
            for doc_id in self._store.index_to_docstore_id.values():
                doc = self._store.docstore.search(doc_id)
                chunks.append(getattr(doc, "metadata", None) or {"text": getattr(doc, "page_content", "")})
            return chunks
        return []

    def _persist(self) -> None:
        if self._store is not None:
            self._store.save_local(self.base_path)
