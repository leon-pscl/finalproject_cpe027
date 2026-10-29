"""Lecture upload and job orchestration."""

from __future__ import annotations

import uuid

from app.config import Settings
from app.contracts import (
    ErrorCode,
    JobStage,
    LectureMetadata,
    LectureStatus,
    UploadCompleteRequest,
    UploadCompleteResponse,
    UploadInitiationRequest,
    UploadInitiationResponse,
)
from app.repositories import LectureRepository
from app.storage import StorageAdapter


class LectureServiceError(Exception):
    def __init__(self, code: ErrorCode, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


SUPPORTED_CONTENT_TYPES: dict[str, str] = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/mp4": ".mp4",
    "audio/x-m4a": ".m4a",
    "audio/aac": ".aac",
    "audio/ogg": ".ogg",
}

DEFAULT_PROCESSING_VERSION = "v1"


def _normalize_content_type(value: str | None) -> str:
    if value is None:
        return ""
    return value.split(";")[0].strip().lower()


class LectureService:
    def __init__(
        self, repository: LectureRepository, storage: StorageAdapter, settings: Settings
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.settings = settings

    def _max_upload_bytes(self) -> int:
        return self.settings.max_upload_mb * 1024 * 1024

    def initiate_upload(
        self,
        owner_id: str,
        request: UploadInitiationRequest,
    ) -> UploadInitiationResponse:
        content_type = _normalize_content_type(request.declared_type)
        extension = SUPPORTED_CONTENT_TYPES.get(content_type)
        if extension is None:
            raise LectureServiceError(
                ErrorCode.UNSUPPORTED_FILE,
                "This file type is not supported for lecture uploads",
            )
        if request.declared_size_bytes > self._max_upload_bytes():
            raise LectureServiceError(
                ErrorCode.FILE_TOO_LARGE,
                f"File exceeds the maximum upload size of {self.settings.max_upload_mb} MB",
            )

        lectures = self.repository.list_lectures(owner_id, limit=200)
        active = [item for item in lectures if item.deleted_at is None]
        if len(active) >= self.settings.per_user_lecture_limit:
            raise LectureServiceError(
                ErrorCode.QUOTA_EXCEEDED,
                "You have reached the maximum number of lectures for this account",
            )

        lecture_id = uuid.uuid4().hex
        storage_path = f"users/{owner_id}/{lecture_id}/source{extension}"
        lecture = self.repository.create_lecture(
            owner_id=owner_id,
            lecture_id=lecture_id,
            title=request.title,
            storage_path=storage_path,
            declared_type=content_type,
            declared_size_bytes=request.declared_size_bytes,
        )
        url, expires_at = self.storage.create_signed_upload_url(
            storage_path=storage_path,
            content_type=content_type,
        )
        return UploadInitiationResponse(
            lecture_id=lecture.lecture_id,
            storage_path=storage_path,
            signed_upload_url=url,
            expires_at=expires_at,
        )

    def _upload_job_id(self, lecture_id: str) -> str:
        from app.repositories import deterministic_job_id

        return deterministic_job_id(lecture_id, DEFAULT_PROCESSING_VERSION)

    def complete_upload(
        self,
        owner_id: str,
        lecture_id: str,
        payload: UploadCompleteRequest,
    ) -> UploadCompleteResponse:
        lecture = self.repository.get_lecture(owner_id, lecture_id)
        if lecture is None:
            raise LectureServiceError(ErrorCode.NOT_FOUND, "Lecture was not found")

        if payload.storage_path != lecture.storage_path:
            raise LectureServiceError(
                ErrorCode.STORED_OBJECT_MISMATCH,
                "The upload did not target the expected storage path",
            )

        if payload.observed_size_bytes is not None and (
            payload.observed_size_bytes <= 0
            or payload.observed_size_bytes > self._max_upload_bytes()
        ):
            raise LectureServiceError(
                ErrorCode.STORED_OBJECT_MISMATCH, "Reported upload size is invalid"
            )

        declared_type = _normalize_content_type(
            lecture.media_metadata.get("content_type", "")
        )
        expected_content_type = declared_type or None
        expected_size = payload.observed_size_bytes
        # Trust the registered declaration when the client omits an observed size.
        if expected_size is None:
            expected_size = int(lecture.media_metadata.get("size_bytes", 0)) or None

        observed_content_type = (
            _normalize_content_type(payload.observed_content_type) or None
        )
        if (
            observed_content_type is not None
            and observed_content_type not in SUPPORTED_CONTENT_TYPES
        ):
            raise LectureServiceError(
                ErrorCode.UNSUPPORTED_FILE, "This file type is not supported"
            )
        if observed_content_type is not None:
            expected_content_type_for_verify = observed_content_type
        else:
            expected_content_type_for_verify = expected_content_type

        try:
            stored = self.storage.verify_object(
                storage_path=lecture.storage_path,
                expected_size=expected_size,
                expected_content_type=expected_content_type_for_verify,
            )
        except (OSError, ValueError) as exc:
            raise LectureServiceError(
                ErrorCode.STORED_OBJECT_MISMATCH,
                f"Stored object verification failed: {exc}",
            ) from exc

        stored_type = _normalize_content_type(stored.content_type)
        if stored_type and stored_type != expected_content_type:
            if (
                observed_content_type is not None
                and stored_type == observed_content_type
            ):
                pass
            elif stored_type != declared_type:
                raise LectureServiceError(
                    ErrorCode.STORED_OBJECT_MISMATCH,
                    "Stored object content type does not match the declared type",
                )
        if stored.size_bytes <= 0:
            raise LectureServiceError(
                ErrorCode.STORED_OBJECT_MISMATCH, "Stored object is empty"
            )
        if (
            payload.observed_size_bytes is not None
            and stored.size_bytes != payload.observed_size_bytes
        ):
            raise LectureServiceError(
                ErrorCode.STORED_OBJECT_MISMATCH,
                "Stored object size does not match the reported size",
            )

        job_id = self._upload_job_id(lecture.lecture_id)
        existing_job = self.repository.get_job(owner_id, lecture.lecture_id, job_id)
        if existing_job is None:
            if (
                self.repository.count_jobs_today(owner_id)
                >= self.settings.per_user_daily_job_limit
            ):
                raise LectureServiceError(
                    ErrorCode.QUOTA_EXCEEDED,
                    "You have reached the daily processing limit; try again later",
                )
            job = self.repository.create_job(
                owner_id=owner_id,
                lecture_id=lecture.lecture_id,
                job_id=job_id,
                processing_version=DEFAULT_PROCESSING_VERSION,
                stage=JobStage.QUEUED,
                state="queued",
            )
        else:
            job = existing_job

        # Keep state visible without claiming progress.
        self.repository.mark_lecture_state(
            owner_id, lecture.lecture_id, LectureStatus.PROCESSING
        )
        return UploadCompleteResponse(
            lecture_id=lecture.lecture_id,
            job_id=job.job_id,
            stage=job.stage,
            message="queued",
        )

    def list_lectures(self, owner_id: str, limit: int = 50) -> list[LectureMetadata]:
        return self.repository.list_lectures(owner_id, limit)

    def get_lecture(self, owner_id: str, lecture_id: str) -> LectureMetadata | None:
        return self.repository.get_lecture(owner_id, lecture_id)

    def retry_lecture(self, owner_id: str, lecture_id: str) -> UploadCompleteResponse:
        from app.contracts import LectureStatus

        lecture = self.repository.get_lecture(owner_id, lecture_id)
        if lecture is None:
            raise LectureServiceError(ErrorCode.NOT_FOUND, "Lecture was not found")
        job_id = self._upload_job_id(lecture.lecture_id)
        job = self.repository.get_job(owner_id, lecture.lecture_id, job_id)
        if job is None:
            raise LectureServiceError(
                ErrorCode.JOB_NOT_RETRYABLE,
                "There is no retryable failure for this lecture",
            )
        if job.state in {"queued", "running"}:
            raise LectureServiceError(
                ErrorCode.JOB_ALREADY_ACTIVE, "Processing is already active"
            )
        if job.state == "completed":
            raise LectureServiceError(
                ErrorCode.JOB_NOT_RETRYABLE, "Completed jobs cannot be retried"
            )
        if job.attempts >= 3:
            raise LectureServiceError(
                ErrorCode.JOB_NOT_RETRYABLE, "Maximum retry attempts have been reached"
            )
        retried = self.repository.retry_job(
            owner_id, lecture.lecture_id, job_id, max_attempts=3
        )
        if not retried:
            raise LectureServiceError(
                ErrorCode.JOB_NOT_RETRYABLE, "This failure is not retryable"
            )
        self.repository.mark_lecture_state(
            owner_id, lecture.lecture_id, LectureStatus.PROCESSING
        )
        refreshed = self.repository.get_job(owner_id, lecture.lecture_id, job_id)
        assert refreshed is not None
        return UploadCompleteResponse(
            lecture_id=lecture.lecture_id,
            job_id=refreshed.job_id,
            stage=refreshed.stage,
            message="queued",
        )
