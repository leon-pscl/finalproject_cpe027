"""Local data access layer.

Every function accepts and enforces ``owner_id``. All Firestore SDK calls are
isolated here so Security Rules (which the Admin SDK bypasses) are mirrored
by explicit ownership checks.

Step 2 adds backend-portable repository implementations so safe local tests do
not require external services.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Any

from app.contracts import (
    ErrorCode,
    JobDocument,
    JobStage,
    LectureMetadata,
    LectureStatus,
)
def _now() -> datetime:
    return datetime.now(UTC)


def _after_seconds(seconds: int) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=seconds)


def _metadata_from_dict(lecture_id: str, data: dict[str, Any]) -> LectureMetadata:
    return LectureMetadata(
        lecture_id=lecture_id,
        owner_id=data["owner_id"],
        title=data.get("title", ""),
        storage_path=data.get("storage_path", ""),
        duration_s=data.get("duration_s"),
        media_metadata=data.get("media_metadata", {}),
        state=LectureStatus(data.get("state", LectureStatus.PENDING.value)),
        active_version=data.get("active_version"),
        deleted_at=data.get("deleted_at"),
        created_at=data.get("created_at", _now()),
    )


def _job_from_dict(job_id: str, lecture_id: str, data: dict[str, Any]) -> JobDocument:
    return JobDocument(
        job_id=job_id,
        lecture_id=lecture_id,
        processing_version=data["processing_version"],
        stage=JobStage(data.get("stage", JobStage.QUEUED.value)),
        state=data.get("state", "queued"),
        attempts=int(data.get("attempts", 0)),
        lease_until=data.get("lease_until"),
        worker_id=data.get("worker_id"),
        safe_error_code=data.get("safe_error_code"),
        timings=data.get("timings", {}),
    )


def _ensure_job_row(
    owner_id: str,
    lecture_id: str,
    job_id: str,
    processing_version: str,
    stage: JobStage = JobStage.QUEUED,
    state: str = "queued",
    attempts: int = 0,
    lease_until: datetime | None = None,
    worker_id: str | None = None,
    safe_error_code: ErrorCode | None = None,
    timings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    timestamp = _now()
    return {
        "job_id": job_id,
        "lecture_id": lecture_id,
        "owner_id": owner_id,
        "processing_version": processing_version,
        "stage": stage.value,
        "state": state,
        "attempts": attempts,
        "lease_until": lease_until,
        "worker_id": worker_id,
        "safe_error_code": safe_error_code.value
        if safe_error_code is not None
        else None,
        "safe_error_message": None,
        "timings": timings or {},
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def _job_created_date(data: dict[str, Any]) -> datetime.date | None:
    value = data.get("created_at")
    if isinstance(value, datetime):
        return value.astimezone(UTC).date() if value.tzinfo else value.date()
    return None


def deterministic_job_id(lecture_id: str, processing_version: str) -> str:
    return f"{lecture_id}_{processing_version}"


class LectureRepository(ABC):
    backend_name: str

    @abstractmethod
    def get_lecture(self, owner_id: str, lecture_id: str) -> LectureMetadata | None:
        raise NotImplementedError

    @abstractmethod
    def list_lectures(self, owner_id: str, limit: int = 50) -> list[LectureMetadata]:
        raise NotImplementedError

    @abstractmethod
    def create_lecture(
        self,
        owner_id: str,
        lecture_id: str,
        title: str,
        storage_path: str,
        declared_type: str,
        declared_size_bytes: int,
    ) -> LectureMetadata:
        raise NotImplementedError

    @abstractmethod
    def list_all_lectures(self, limit: int = 200) -> list[LectureMetadata]:
        raise NotImplementedError

    @abstractmethod
    def get_job(
        self, owner_id: str, lecture_id: str, job_id: str
    ) -> JobDocument | None:
        raise NotImplementedError

    @abstractmethod
    def create_job(
        self,
        owner_id: str,
        lecture_id: str,
        job_id: str,
        processing_version: str,
        *,
        stage: JobStage = JobStage.QUEUED,
        state: str = "queued",
        attempts: int = 0,
        lease_until: datetime | None = None,
        worker_id: str | None = None,
        safe_error_code: ErrorCode | None = None,
        timings: dict[str, Any] | None = None,
    ) -> JobDocument:
        raise NotImplementedError

    @abstractmethod
    def list_jobs(
        self,
        owner_id: str | None = None,
        lecture_id: str | None = None,
        limit: int = 200,
    ) -> list[JobDocument]:
        raise NotImplementedError

    @abstractmethod
    def claim_job(
        self,
        owner_id: str,
        lecture_id: str,
        job_id: str,
        worker_id: str,
        lease_seconds: int = 60,
        max_attempts: int = 3,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def heartbeat_job(
        self,
        owner_id: str,
        lecture_id: str,
        job_id: str,
        worker_id: str,
        lease_seconds: int = 60,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def update_job_stage(
        self,
        owner_id: str,
        lecture_id: str,
        job_id: str,
        stage: JobStage,
        timings: dict[str, float] | None = None,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def fail_job(
        self,
        owner_id: str,
        lecture_id: str,
        job_id: str,
        code: ErrorCode,
        message: str,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def retry_job(
        self,
        owner_id: str,
        lecture_id: str,
        job_id: str,
        max_attempts: int = 3,
    ) -> bool:
        raise NotImplementedError

    def mark_lecture_state(
        self, owner_id: str, lecture_id: str, state: LectureStatus
    ) -> bool:
        raise NotImplementedError

    def count_jobs_today(self, owner_id: str) -> int:
        return sum(1 for job in self.list_jobs(owner_id=owner_id))

    def update_job_state(
        self,
        owner_id: str,
        lecture_id: str,
        job_id: str,
        *,
        state: str | None = None,
        stage: JobStage | None = None,
        lease_until: datetime | None = None,
        worker_id: str | None = None,
        attempts: int | None = None,
        safe_error_code: ErrorCode | None = None,
        timings: dict[str, Any] | None = None,
        lease_seconds: int | None = None,
    ) -> bool:
        raise NotImplementedError


class InMemoryLectureRepository(LectureRepository):
    backend_name = "memory"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._lectures: dict[str, dict[str, Any]] = {}
        self._jobs: dict[str, dict[str, Any]] = {}

    def get_lecture(self, owner_id: str, lecture_id: str) -> LectureMetadata | None:
        with self._lock:
            data = self._lectures.get(lecture_id)
            if not data or data.get("owner_id") != owner_id:
                return None
            return _metadata_from_dict(lecture_id, data)

    def list_lectures(self, owner_id: str, limit: int = 50) -> list[LectureMetadata]:
        if limit <= 0 or limit > 200:
            raise ValueError("limit must be between 1 and 200")
        with self._lock:
            result = [
                _metadata_from_dict(lecture_id, data)
                for lecture_id, data in self._lectures.items()
                if data.get("owner_id") == owner_id
            ]
        result.sort(key=lambda item: item.created_at, reverse=True)
        return result[:limit]

    def list_all_lectures(self, limit: int = 200) -> list[LectureMetadata]:
        with self._lock:
            result = [
                _metadata_from_dict(item, data) for item, data in self._lectures.items()
            ]
        result.sort(key=lambda item: item.created_at, reverse=True)
        return result[:limit]

    def create_lecture(
        self,
        owner_id: str,
        lecture_id: str,
        title: str,
        storage_path: str,
        declared_type: str,
        declared_size_bytes: int,
    ) -> LectureMetadata:
        with self._lock:
            self._lectures[lecture_id] = {
                "owner_id": owner_id,
                "title": title,
                "storage_path": storage_path,
                "media_metadata": {
                    "content_type": declared_type,
                    "size_bytes": declared_size_bytes,
                },
                "state": LectureStatus.PENDING.value,
                "active_version": None,
                "deleted_at": None,
                "created_at": _now(),
            }
        return self.get_lecture(owner_id, lecture_id)  # type: ignore[return-value]

    def mark_lecture_state(
        self, owner_id: str, lecture_id: str, state: LectureStatus
    ) -> bool:
        with self._lock:
            data = self._lectures.get(lecture_id)
            if not data or data.get("owner_id") != owner_id:
                return False
            data["state"] = state.value
            data["updated_at"] = _now()
        return True

    def get_job(
        self, owner_id: str, lecture_id: str, job_id: str
    ) -> JobDocument | None:
        lecture = self.get_lecture(owner_id, lecture_id)
        if lecture is None:
            return None
        with self._lock:
            data = self._jobs.get(job_id)
            if (
                not data
                or data.get("lecture_id") != lecture_id
                or data.get("owner_id") != owner_id
            ):
                return None
            return _job_from_dict(job_id, lecture_id, data)

    def create_job(
        self,
        owner_id: str,
        lecture_id: str,
        job_id: str,
        processing_version: str,
        *,
        stage: JobStage = JobStage.QUEUED,
        state: str = "queued",
        attempts: int = 0,
        lease_until: datetime | None = None,
        worker_id: str | None = None,
        safe_error_code: ErrorCode | None = None,
        timings: dict[str, Any] | None = None,
    ) -> JobDocument:
        with self._lock:
            existing = self._jobs.get(job_id)
            if existing is not None:
                if (
                    existing.get("owner_id") != owner_id
                    or existing.get("lecture_id") != lecture_id
                ):
                    raise ValueError("Job is not accessible")
                return _job_from_dict(job_id, lecture_id, existing)
            data = _ensure_job_row(
                owner_id,
                lecture_id,
                job_id,
                processing_version,
                stage,
                state,
                attempts,
                lease_until,
                worker_id,
                safe_error_code,
                timings,
            )
            self._jobs[job_id] = data
        result = self.get_job(owner_id, lecture_id, job_id)
        if result is None:
            raise RuntimeError("Job was not persisted")
        return result

    def list_jobs(
        self,
        owner_id: str | None = None,
        lecture_id: str | None = None,
        limit: int = 200,
    ) -> list[JobDocument]:
        del limit
        result: list[JobDocument] = []
        with self._lock:
            for job_id, data in self._jobs.items():
                if lecture_id is not None and data.get("lecture_id") != lecture_id:
                    continue
                if owner_id is not None and data.get("owner_id") != owner_id:
                    continue
                result.append(_job_from_dict(job_id, data["lecture_id"], data))
        return result

    def count_jobs_today(self, owner_id: str) -> int:
        today = _now().date()
        with self._lock:
            return sum(
                1
                for data in self._jobs.values()
                if data.get("owner_id") == owner_id and _job_created_date(data) == today
            )

    def claim_job(
        self,
        owner_id: str,
        lecture_id: str,
        job_id: str,
        worker_id: str,
        lease_seconds: int = 60,
        max_attempts: int = 3,
    ) -> bool:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        with self._lock:
            data = self._jobs.get(job_id)
            if (
                not data
                or data.get("lecture_id") != lecture_id
                or data.get("owner_id") != owner_id
            ):
                return False
            state = data.get("state", "queued")
            lease_until = data.get("lease_until")
            claimable = state == "queued" or (
                state == "running" and (lease_until is None or lease_until <= _now())
            )
            if not claimable:
                return False
            attempts = int(data.get("attempts", 0))
            if attempts >= max_attempts:
                return False
            data["state"] = "running"
            data["stage"] = data.get("stage", JobStage.QUEUED.value)
            data["worker_id"] = worker_id
            data["attempts"] = attempts + 1
            data["lease_until"] = _after_seconds(lease_seconds)
            data["updated_at"] = _now()
        return True

    def heartbeat_job(
        self,
        owner_id: str,
        lecture_id: str,
        job_id: str,
        worker_id: str,
        lease_seconds: int = 60,
    ) -> bool:
        job = self.get_job(owner_id, lecture_id, job_id)
        if job is None or job.worker_id != worker_id or job.state != "running":
            return False
        with self._lock:
            data = self._jobs.get(job_id)
            if data is None:
                return False
            data["lease_until"] = _after_seconds(lease_seconds)
            data["updated_at"] = _now()
        return True

    def update_job_stage(
        self,
        owner_id: str,
        lecture_id: str,
        job_id: str,
        stage: JobStage,
        timings: dict[str, float] | None = None,
    ) -> bool:
        job = self.get_job(owner_id, lecture_id, job_id)
        if job is None:
            return False
        with self._lock:
            data = self._jobs.get(job_id)
            if data is None:
                return False
            data["stage"] = stage.value
            data["updated_at"] = _now()
            if timings:
                existing = data.get("timings", {})
                data["timings"] = {**existing, **timings}
        return True

    def fail_job(
        self,
        owner_id: str,
        lecture_id: str,
        job_id: str,
        code: ErrorCode,
        message: str,
    ) -> bool:
        job = self.get_job(owner_id, lecture_id, job_id)
        if job is None:
            return False
        with self._lock:
            data = self._jobs.get(job_id)
            if data is None:
                return False
            data["state"] = "failed"
            data["stage"] = JobStage.FAILED.value
            data["safe_error_code"] = code.value
            data["safe_error_message"] = message
            data["updated_at"] = _now()
        return True

    def retry_job(
        self,
        owner_id: str,
        lecture_id: str,
        job_id: str,
        max_attempts: int = 3,
    ) -> bool:
        job = self.get_job(owner_id, lecture_id, job_id)
        if job is None or job.state not in {"failed", "cancelled"}:
            return False
        if job.attempts >= max_attempts:
            return False
        with self._lock:
            data = self._jobs.get(job_id)
            if data is None:
                return False
            data["state"] = "queued"
            data["stage"] = JobStage.QUEUED.value
            data["worker_id"] = None
            data["lease_until"] = None
            data["safe_error_code"] = None
            data["safe_error_message"] = None
            data["updated_at"] = _now()
        return True

    def update_job_state(
        self,
        owner_id: str,
        lecture_id: str,
        job_id: str,
        *,
        state: str | None = None,
        stage: JobStage | None = None,
        lease_until: datetime | None = None,
        worker_id: str | None = None,
        attempts: int | None = None,
        safe_error_code: ErrorCode | None = None,
        timings: dict[str, Any] | None = None,
        lease_seconds: int | None = None,
    ) -> bool:
        job = self.get_job(owner_id, lecture_id, job_id)
        if job is None:
            return False
        with self._lock:
            data = self._jobs.get(job_id)
            if data is None:
                return False
            if state is not None:
                data["state"] = state
            if stage is not None:
                data["stage"] = stage.value
            if lease_until is not None:
                data["lease_until"] = lease_until
            if worker_id is not None:
                data["worker_id"] = worker_id
            if attempts is not None:
                data["attempts"] = attempts
            if safe_error_code is not None:
                data["safe_error_code"] = safe_error_code.value
            if timings:
                existing = data.get("timings", {})
                data["timings"] = {**existing, **timings}
            if lease_seconds is not None:
                data["lease_until"] = _after_seconds(lease_seconds)
            data["updated_at"] = _now()
        return True

