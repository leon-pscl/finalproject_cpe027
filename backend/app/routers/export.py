from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import Annotated
from app.storage import StorageAdapter

from app.auth import VerifiedUser
from app.dependencies import get_current_user, get_lecture_service, get_repository, get_storage
from app.repositories import LectureRepository
from app.services.export_service import ExportService

router = APIRouter(tags=["export"])

@router.get("/lectures/{lecture_id}/export")
def export_lecture(
    lecture_id: str,
    user: Annotated[VerifiedUser, Depends(get_current_user)],
    repository: Annotated[LectureRepository, Depends(get_repository)],
    storage: Annotated[StorageAdapter, Depends(get_storage)],
):
    lecture = repository.get_lecture(user.uid, lecture_id)
    if lecture is None:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Lecture not found"})
    service = ExportService(storage, storage.settings.local_storage_root)
    zip_bytes = service.bundle(user.uid, lecture_id)
    return StreamingResponse(
        iter([zip_bytes]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={lecture_id}.zip"},
    )
