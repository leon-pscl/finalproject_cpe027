from fastapi import APIRouter, Depends, HTTPException
from app.storage import StorageAdapter


from app.auth import VerifiedUser
from app.dependencies import get_current_user, get_repository, get_storage
from app.repositories import LectureRepository
from app.contracts import LectureStatus
import os, shutil

router = APIRouter(tags=["lectures"])

@router.delete("/lectures/{lecture_id}", status_code=204)
def delete_lecture(
    lecture_id: str,
    user: Annotated[VerifiedUser, Depends(get_current_user)],
    repository: Annotated[LectureRepository, Depends(get_repository)],
    storage: Annotated[StorageAdapter, Depends(get_storage)],
) -> None:
    # Verify lecture exists
    lecture = repository.get_lecture(user.uid, lecture_id)
    if lecture is None:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Lecture not found"})
    # Delete local storage folder if applicable
    if hasattr(storage, "_full_path"):
        # Assume LocalStorageAdapter
        lecture_dir = storage._full_path(f"users/{user.uid}/{lecture_id}")
        shutil.rmtree(lecture_dir, ignore_errors=True)
    # Delete FAISS index folder
    vec_dir = os.path.join(storage.settings.local_storage_root, "vectors", lecture_id)
    shutil.rmtree(vec_dir, ignore_errors=True)
    # Mark lecture as deleted (state transition)
    repository.mark_lecture_state(user.uid, lecture_id, LectureStatus.DELETED)
    return None
