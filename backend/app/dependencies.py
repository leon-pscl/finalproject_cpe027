"""FastAPI dependency wiring for Step 2."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.auth import AuthError, VerifiedUser, verify_id_token
from app.config import Settings, get_settings
from app.contracts import ErrorCode
from app.repositories import (
    FirestoreLectureRepository,
    InMemoryLectureRepository,
    LectureRepository,
)
from app.services.lecture_service import LectureService, LectureServiceError
from app.storage import FirebaseStorageAdapter, LocalStorageAdapter, StorageAdapter

_repository_cache: dict[int, LectureRepository] = {}


def clear_repository_cache() -> None:
    _repository_cache.clear()


def create_repository(settings: Settings | None = None) -> LectureRepository:
    if settings is None:
        settings = get_settings()
    backend = getattr(settings, "repository_backend", "auto")
    if backend == "memory":
        return InMemoryLectureRepository()
    if backend == "firestore":
        return FirestoreLectureRepository()
    # auto: prefer Firestore when Firebase configuration is present.
    if (
        settings.firebase_project_id
        or settings.firestore_emulator_host
        or settings.firebase_credentials_path
    ):
        return FirestoreLectureRepository()
    return InMemoryLectureRepository()


def get_settings_dependency() -> Settings:
    return get_settings()


def get_repository(
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> LectureRepository:
    key = id(settings)
    cached = _repository_cache.get(key)
    if cached is None:
        cached = create_repository(settings)
        _repository_cache[key] = cached
    return cached


def create_storage(settings: Settings) -> StorageAdapter:
    if (
        settings.repository_backend == "firestore"
        or settings.firebase_project_id
        or settings.firestore_emulator_host
        or settings.firebase_credentials_path
        or settings.firebase_storage_bucket
    ):
        return FirebaseStorageAdapter(settings)
    return LocalStorageAdapter(settings)


def get_storage(
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> StorageAdapter:
    return create_storage(settings)


def create_lecture_service(
    repository: LectureRepository,
    storage: StorageAdapter,
    settings: Settings,
) -> LectureService:
    return LectureService(repository, storage, settings)


def get_lecture_service(
    repository: Annotated[LectureRepository, Depends(get_repository)],
    storage: Annotated[StorageAdapter, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> LectureService:
    return create_lecture_service(repository, storage, settings)


def _error_status(code: ErrorCode) -> int:
    return {
        ErrorCode.AUTH_REQUIRED: status.HTTP_401_UNAUTHORIZED,
        ErrorCode.SESSION_EXPIRED: status.HTTP_401_UNAUTHORIZED,
        ErrorCode.AUTH_INVALID: status.HTTP_401_UNAUTHORIZED,
        ErrorCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
        ErrorCode.FORBIDDEN: status.HTTP_403_FORBIDDEN,
        ErrorCode.QUOTA_EXCEEDED: status.HTTP_429_TOO_MANY_REQUESTS,
        ErrorCode.UNSUPPORTED_FILE: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        ErrorCode.FILE_TOO_LARGE: status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        ErrorCode.STORED_OBJECT_MISMATCH: status.HTTP_422_UNPROCESSABLE_ENTITY,
        ErrorCode.INVALID_REQUEST: status.HTTP_422_UNPROCESSABLE_ENTITY,
        ErrorCode.JOB_ALREADY_ACTIVE: status.HTTP_409_CONFLICT,
        ErrorCode.JOB_NOT_RETRYABLE: status.HTTP_409_CONFLICT,
        ErrorCode.PROCESSING_FAILED: status.HTTP_500_INTERNAL_SERVER_ERROR,
    }.get(code, status.HTTP_400_BAD_REQUEST)


def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> VerifiedUser:
    try:
        return verify_id_token(authorization=authorization)
    except AuthError as exc:
        raise HTTPException(
            status_code=_error_status(exc.code),
            detail={"error_code": exc.code.value, "message": exc.detail},
        ) from exc


def translate_service_error(exc: LectureServiceError) -> HTTPException:
    return HTTPException(
        status_code=_error_status(exc.code),
        detail={"error_code": exc.code.value, "message": exc.detail},
    )
