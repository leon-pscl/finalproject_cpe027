"""Lecture upload, status, and retry endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import VerifiedUser
from app.contracts import (
    LectureMetadata,
    UploadCompleteRequest,
    UploadCompleteResponse,
    UploadInitiationRequest,
    UploadInitiationResponse,
)
from app.dependencies import (
    LectureServiceError,
    get_current_user,
    get_lecture_service,
    translate_service_error,
)
from app.services.lecture_service import LectureService

router = APIRouter(tags=["lectures"])


@router.post("/lectures/uploads", response_model=UploadInitiationResponse)
def initiate_upload(
    request: UploadInitiationRequest,
    service: Annotated[LectureService, Depends(get_lecture_service)],
    user: Annotated[VerifiedUser, Depends(get_current_user)],
):
    try:
        return service.initiate_upload(user.uid, request)
    except LectureServiceError as exc:
        raise translate_service_error(exc)


@router.get("/lectures", response_model=list[LectureMetadata])
def list_lectures(
    service: Annotated[LectureService, Depends(get_lecture_service)],
    user: Annotated[VerifiedUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    try:
        return service.list_lectures(user.uid, limit)
    except LectureServiceError as exc:
        raise translate_service_error(exc)


@router.get("/lectures/{lecture_id}", response_model=LectureMetadata)
def get_lecture(
    lecture_id: str,
    service: Annotated[LectureService, Depends(get_lecture_service)],
    user: Annotated[VerifiedUser, Depends(get_current_user)],
):
    lecture = service.get_lecture(user.uid, lecture_id)
    if lecture is None:
        from app.contracts import ErrorCode

        raise HTTPException(
            status_code=404,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "message": "Lecture was not found",
            },
        )
    return lecture


@router.post(
    "/lectures/{lecture_id}/upload-complete",
    response_model=UploadCompleteResponse,
    status_code=202,
)
def upload_complete(
    lecture_id: str,
    request: UploadCompleteRequest,
    service: Annotated[LectureService, Depends(get_lecture_service)],
    user: Annotated[VerifiedUser, Depends(get_current_user)],
):
    try:
        return service.complete_upload(user.uid, lecture_id, request)
    except LectureServiceError as exc:
        raise translate_service_error(exc)


@router.post(
    "/lectures/{lecture_id}/retry",
    response_model=UploadCompleteResponse,
    status_code=202,
)
def retry_lecture(
    lecture_id: str,
    service: Annotated[LectureService, Depends(get_lecture_service)],
    user: Annotated[VerifiedUser, Depends(get_current_user)],
):
    try:
        return service.retry_lecture(user.uid, lecture_id)
    except LectureServiceError as exc:
        raise translate_service_error(exc)
