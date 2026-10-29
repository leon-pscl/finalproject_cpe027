from __future__ import annotations

import json
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException

from app.adapters import adapter_bundle
from app.auth import VerifiedUser
from app.config import get_settings
from app.contracts import NoteEntry
from app.dependencies import get_current_user, get_repository, get_storage
from app.repositories import LectureRepository
from app.storage import StorageAdapter
from app.vector_store import FAISSVectorStore

router = APIRouter(tags=["notes"])


def _get_lecture_chunks(storage: StorageAdapter, owner_id: str, lecture_id: str) -> List[dict]:
    settings = getattr(storage, "settings", None) or get_settings()
    try:
        vector_store = FAISSVectorStore(settings.local_storage_root, lecture_id)
        if vector_store.metadata:
            return list(vector_store.metadata.values())
    except Exception:
        pass

    try:
        data_bytes, _ = storage.read_object(f"users/{owner_id}/{lecture_id}/chunks.json")
        return json.loads(data_bytes)
    except Exception:
        return []


@router.post("/lectures/{lecture_id}/notes", response_model=List[NoteEntry])
@router.get("/lectures/{lecture_id}/notes", response_model=List[NoteEntry])
def get_or_generate_notes(
    lecture_id: str,
    user: Annotated[VerifiedUser, Depends(get_current_user)],
    repository: Annotated[LectureRepository, Depends(get_repository)],
    storage: Annotated[StorageAdapter, Depends(get_storage)],
) -> List[NoteEntry]:
    # Verify lecture exists
    lecture = repository.get_lecture(user.uid, lecture_id)
    if lecture is None:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "NOT_FOUND", "message": "Lecture not found"},
        )

    # Check if saved notes already exist
    notes_path = f"users/{user.uid}/{lecture_id}/notes.json"
    try:
        data_bytes, _ = storage.read_object(notes_path)
        cached = json.loads(data_bytes)
        if cached:
            return [NoteEntry(**item) for item in cached]
    except Exception:
        pass

    # Retrieve all stored chunks
    all_chunks = _get_lecture_chunks(storage, user.uid, lecture_id)
    if not all_chunks:
        # Return fallback note if no chunks are indexed yet
        return [
            NoteEntry(
                note_id="empty-note",
                lecture_id=lecture_id,
                version="v1",
                section="Overview",
                title="Lecture in Progress",
                description="Notes will be generated once lecture processing completes.",
                supporting_segment_ids=[],
            )
        ]

    # Generate notes using notes adapter
    notes_gen = adapter_bundle()["notes"]
    notes = notes_gen.generate(all_chunks, {"lecture_id": lecture_id, "processing_version": "v1"})

    # Cache generated notes
    try:
        storage.save_object(
            notes_path,
            json.dumps([n.dict() for n in notes], indent=2).encode("utf-8"),
            "application/json",
        )
    except Exception:
        pass

    return notes
