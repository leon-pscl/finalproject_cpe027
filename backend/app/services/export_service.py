import io
import zipfile
import os
from typing import Any

from app.storage import StorageAdapter

class ExportService:
    """Bundle lecture artifacts (transcript, chunks, FAISS index) into a zip file."""

    def __init__(self, storage: StorageAdapter, root: str):
        self.storage = storage
        self.root = root

    def bundle(self, owner_id: str, lecture_id: str) -> bytes:
        # Gather paths relative to storage root
        base_path = f"users/{owner_id}/{lecture_id}"
        files = {
            "transcript.json": f"{base_path}/transcript.json",
            "chunks.json": f"{base_path}/chunks.json",
        }
        # Include FAISS index and metadata if present
        faiss_root = os.path.join(self.storage.settings.local_storage_root, "vectors", lecture_id)
        index_path = os.path.join(faiss_root, "index.faiss")
        meta_path = os.path.join(faiss_root, "metadata.json")
        if os.path.isfile(index_path):
            files["faiss/index.faiss"] = index_path
        if os.path.isfile(meta_path):
            files["faiss/metadata.json"] = meta_path

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for arcname, src in files.items():
                # If src is a storage path (for local storage) read via adapter, else read file directly
                if src.startswith(self.storage.settings.local_storage_root):
                    with open(src, "rb") as f:
                        data = f.read()
                else:
                    data, _ = self.storage.read_object(src)
                zf.writestr(arcname, data)
        return buffer.getvalue()
