import os
import json
from typing import List, Tuple
import numpy as np
import faiss

class FAISSVectorStore:
    """Simple FAISS index persisted to disk.

    * Each lecture gets its own sub‑directory under the configured
      `local_storage_root` (e.g., `<root>/vectors/<lecture_id>/`).
    * Vectors are 384‑dimensional (the MiniLM model).
    * Metadata (chunk dicts) are stored in a JSON file keyed by the FAISS
      internal vector ID so we can retrieve the original chunk information
      after a similarity search.
    """
    def __init__(self, storage_root: str, lecture_id: str, dim: int = 384) -> None:
        self.dim = dim
        self.base_path = os.path.join(storage_root, "vectors", lecture_id)
        os.makedirs(self.base_path, exist_ok=True)
        self.index_path = os.path.join(self.base_path, "index.faiss")
        self.meta_path = os.path.join(self.base_path, "metadata.json")
        self._load_or_create()

    def _load_or_create(self) -> None:
        if os.path.exists(self.index_path) and os.path.exists(self.meta_path):
            self.index = faiss.read_index(self.index_path)
            with open(self.meta_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)  # {str(vector_id): chunk_dict}
        else:
            self.index = faiss.IndexFlatL2(self.dim)
            self.metadata = {}
            self._persist()

    def _persist(self) -> None:
        faiss.write_index(self.index, self.index_path)
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)

    def add(self, chunks: List[dict], vectors: List[List[float]]) -> None:
        """Add new chunks and their embeddings to the index.

        * `chunks` – list of plain dictionaries (the result of `Chunk.dict()`).
        * `vectors` – list of 384‑dim float lists.
        """
        np_vectors = np.array(vectors, dtype="float32")
        start_id = self.index.ntotal
        self.index.add(np_vectors)
        # FAISS assigns IDs sequentially starting at 0; we can map them
        for i, chunk in enumerate(chunks):
            vec_id = start_id + i
            self.metadata[str(vec_id)] = chunk
        self._persist()

    def query(self, query_vec: List[float], top_k: int = 5) -> List[Tuple[dict, float]]:
        """Return the top‑k (chunk_dict, similarity) pairs for a query vector.

        Similarity is computed as `1 / (1 + L2_distance)` so larger = more similar.
        """
        q = np.array([query_vec], dtype="float32")
        distances, ids = self.index.search(q, top_k)
        results: List[Tuple[dict, float]] = []
        for dist, idx in zip(distances[0], ids[0]):
            if idx == -1:
                continue
            chunk = self.metadata.get(str(idx))
            if chunk is None:
                continue
            similarity = 1.0 / (1.0 + float(dist))
            results.append((chunk, similarity))
        return results
