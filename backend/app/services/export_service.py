from __future__ import annotations

import io
import os
import zipfile

from app.config import get_settings
from app.storage import StorageAdapter


class ExportService:
    """Bundle lecture artifacts (transcript, chunks, FAISS index) into a zip file."""

    def __init__(self, storage: StorageAdapter, root: str | None = None):
        self.storage = storage
        self.root = root or getattr(storage, "settings", None) or get_settings().local_storage_root
        if hasattr(self.root, "local_storage_root"):
            self.root = self.root.local_storage_root

    def bundle(self, owner_id: str, lecture_id: str) -> bytes:
        # Gather paths relative to storage root
        base_path = f"users/{owner_id}/{lecture_id}"
        files = {
            "transcript.json": f"{base_path}/transcript.json",
            "chunks.json": f"{base_path}/chunks.json",
        }
        # Include FAISS index and metadata if present
        faiss_root = os.path.join(str(self.root), "vectors", lecture_id)
        index_path = os.path.join(faiss_root, "index.faiss")
        meta_path = os.path.join(faiss_root, "metadata.json")
        if os.path.isfile(index_path):
            files["faiss/index.faiss"] = index_path
        if os.path.isfile(meta_path):
            files["faiss/metadata.json"] = meta_path

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for arcname, src in files.items():
                try:
                    if os.path.isfile(src):
                        with open(src, "rb") as f:
                            data = f.read()
                    else:
                        data, _ = self.storage.read_object(src)
                    zf.writestr(arcname, data)
                except Exception:
                    # Skip missing files in zip bundle
                    continue
        return buffer.getvalue()
