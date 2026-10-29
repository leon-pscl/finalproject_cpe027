from fastapi import APIRouter, Depends, HTTPException
from app.storage import StorageAdapter
from typing import Annotated, List

from app.auth import VerifiedUser
from app.adapters import adapter_bundle
from app.dependencies import get_current_user, get_lecture_service, get_repository, get_storage
from app.repositories import LectureRepository
from app.contracts import NoteEntry, Chunk
import json


router = APIRouter(tags=["notes"])

@router.post("/lectures/{lecture_id}/notes", response_model=List[NoteEntry])
def generate_notes(
    lecture_id: str,
    user: Annotated[VerifiedUser, Depends(get_current_user)],
    repository: Annotated[LectureRepository, Depends(get_repository)],
    storage: Annotated[StorageAdapter, Depends(get_storage)],
) -> List[NoteEntry]:
    # Verify lecture exists
    lecture = repository.get_lecture(user.uid, lecture_id)
    if lecture is None:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Lecture not found"})
    # Load all chunks (FAISS) for the lecture, with fallback if FAISS unavailable
    from app.vector_store import FAISSVectorStore, faiss
    vector_store = FAISSVectorStore(storage.settings.local_storage_root, lecture_id)
    if faiss is None or getattr(vector_store, "index", None) is None:
        # Fallback: read stored chunks JSON directly from storage
        data_bytes, _ = storage.read_object(f"users/{user.uid}/{lecture_id}/chunks.json")
        chunks_json = data_bytes.decode()
        all_chunks = [Chunk(**c) for c in json.loads(chunks_json)]
    else:
        # Retrieve all stored chunks (no limit) – fetch raw metadata entries via FAISS
        all_chunks = [chunk for chunk, _ in vector_store.query(vector_store.index.reconstruct_n(0, vector_store.index.ntotal), top_k=vector_store.index.ntotal)]
    # Use notes generator
    notes_gen = adapter_bundle()["notes"]
    notes = notes_gen.generate(all_chunks, {"lecture_id": lecture_id, "processing_version": "v1"})
    return notes
