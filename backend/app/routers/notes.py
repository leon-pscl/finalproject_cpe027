from fastapi import APIRouter, Depends, HTTPException
from app.storage import StorageAdapter
from typing import Annotated, List

from app.auth import VerifiedUser
from app.adapters import adapter_bundle
from app.dependencies import get_current_user, get_lecture_service, get_repository, get_storage
from app.repositories import LectureRepository
from app.contracts import NoteEntry

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
    # Load all chunks (FAISS) for the lecture
    from app.vector_store import FAISSVectorStore
    vector_store = FAISSVectorStore(storage.settings.local_storage_root, lecture_id)
    # Retrieve all stored chunks (no limit) – we fetch the raw metadata entries
    all_chunks = [chunk for chunk, _ in vector_store.query(vector_store.index.reconstruct_n(0, vector_store.index.ntotal), top_k=vector_store.index.ntotal)]
    # Use notes generator
    notes_gen = adapter_bundle()["notes"]
    notes = notes_gen.generate(all_chunks, {"lecture_id": lecture_id, "processing_version": "v1"})
    return notes
