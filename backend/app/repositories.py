"""Firestore access layer.

Every function accepts and enforces ``owner_id``. All Firestore SDK calls are
isolated here so Security Rules (which the Admin SDK bypasses) are mirrored
by explicit ownership checks.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.contracts import (
    ErrorCode,
    JobDocument,
    JobStage,
    LectureMetadata,
    LectureStatus,
)
from app.firebase import get_firestore_client


def _now() -> datetime:
    return datetime.now(UTC)


def _after_seconds(seconds: int) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=seconds)


def _transactional_decorator() -> Any:
    try:
        from google.cloud.firestore_v1.transaction import (
            transactional as real_transactional,
        )

        return real_transactional
    except ImportError:

        def _passthrough(func):
            return func

        return _passthrough


def _lecture_ref(lecture_id: str) -> Any:
    return get_firestore_client().collection("lectures").document(lecture_id)


def get_lecture(owner_id: str, lecture_id: str) -> LectureMetadata | None:
    snapshot = _lecture_ref(lecture_id).get()
    if not snapshot.exists:
        return None
    data = snapshot.to_dict() or {}
    if data.get("owner_id") != owner_id:
        return None
    return LectureMetadata(
        lecture_id=lecture_id,
        owner_id=data["owner_id"],
        title=data.get("title", ""),
        storage_path=data.get("storage_path", ""),
        duration_s=data.get("duration_s"),
        media_metadata=data.get("media_metadata", {}),
        state=LectureStatus(data.get("state", LectureStatus.PENDING)),
        active_version=data.get("active_version"),
        deleted_at=data.get("deleted_at"),
        created_at=data.get("created_at", _now()),
    )


def list_lectures(owner_id: str, limit: int = 50) -> list[LectureMetadata]:
    if limit <= 0 or limit > 200:
        raise ValueError("limit must be between 1 and 200")
    query = (
        get_firestore_client()
        .collection("lectures")
        .where("owner_id", "==", owner_id)
        .order_by("created_at", direction="DESCENDING")
        .limit(limit)
    )
    result: list[LectureMetadata] = []
    for snapshot in query.stream():
        data = snapshot.to_dict() or {}
        result.append(
            LectureMetadata(
                lecture_id=snapshot.id,
                owner_id=data["owner_id"],
                title=data.get("title", ""),
                storage_path=data.get("storage_path", ""),
                duration_s=data.get("duration_s"),
                media_metadata=data.get("media_metadata", {}),
                state=LectureStatus(data.get("state", LectureStatus.PENDING)),
                active_version=data.get("active_version"),
                deleted_at=data.get("deleted_at"),
                created_at=data.get("created_at", _now()),
            )
        )
    return result


def create_lecture(
    owner_id: str,
    lecture_id: str,
    title: str,
    storage_path: str,
    declared_type: str,
    declared_size_bytes: int,
) -> LectureMetadata:
    now = _now()
    data = {
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
        "created_at": now,
    }
    _lecture_ref(lecture_id).set(data, merge=False)
    return get_lecture(owner_id, lecture_id)  # type: ignore[return-value]


def job_ref(lecture_id: str, job_id: str) -> Any:
    return _lecture_ref(lecture_id).collection("jobs").document(job_id)


def deterministic_job_id(lecture_id: str, processing_version: str) -> str:
    return f"{lecture_id}_{processing_version}"


def get_job(owner_id: str, lecture_id: str, job_id: str) -> JobDocument | None:
    lecture = get_lecture(owner_id, lecture_id)
    if lecture is None:
        return None
    snapshot = job_ref(lecture_id, job_id).get()
    if not snapshot.exists:
        return None
    data = snapshot.to_dict() or {}
    return JobDocument(
        job_id=snapshot.id,
        lecture_id=lecture_id,
        processing_version=data["processing_version"],
        stage=JobStage(data.get("stage", JobStage.QUEUED)),
        state=data.get("state", "queued"),
        attempts=data.get("attempts", 0),
        lease_until=data.get("lease_until"),
        worker_id=data.get("worker_id"),
        safe_error_code=data.get("safe_error_code"),
        timings=data.get("timings", {}),
    )


def claim_job(
    owner_id: str,
    lecture_id: str,
    job_id: str,
    worker_id: str,
    lease_seconds: int = 60,
    max_attempts: int = 3,
) -> bool:
    """Atomically claim a queued or stale-lease job. Returns True on success."""
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")

    client = get_firestore_client()
    transaction = client.transaction()
    transactional = _transactional_decorator()
    ref = job_ref(lecture_id, job_id)

    @transactional()  # guard is applied if SDK is available
    def _claim(transaction: Any) -> bool:
        snapshot = ref.get(transaction=transaction)
        if not snapshot.exists:
            return False
        data = snapshot.to_dict() or {}
        lecture_snapshot = _lecture_ref(lecture_id).get(transaction=transaction)
        if (
            not lecture_snapshot.exists
            or (lecture_snapshot.to_dict() or {}).get("owner_id") != owner_id
        ):
            return False
        state = data.get("state", "queued")
        now = _now()
        lease_until = data.get("lease_until")
        claimable = state == "queued" or (
            state == "running" and (lease_until is None or lease_until <= now)
        )
        if not claimable:
            return False
        attempts = int(data.get("attempts", 0))
        if attempts >= max_attempts:
            return False
        transaction.update(
            ref,
            {
                "state": "running",
                "stage": data.get("stage", JobStage.QUEUED.value),
                "worker_id": worker_id,
                "attempts": attempts + 1,
                "lease_until": _after_seconds(lease_seconds),
                "updated_at": now,
            },
        )
        return True

    return bool(_claim(transaction))


def heartbeat_job(
    owner_id: str, lecture_id: str, job_id: str, worker_id: str, lease_seconds: int = 60
) -> bool:
    job = get_job(owner_id, lecture_id, job_id)
    if job is None or job.worker_id != worker_id or job.state != "running":
        return False
    job_ref(lecture_id, job_id).update(
        {"lease_until": _after_seconds(lease_seconds), "updated_at": _now()}
    )
    return True


def update_job_stage(
    owner_id: str,
    lecture_id: str,
    job_id: str,
    stage: JobStage,
    timings: dict[str, float] | None = None,
) -> None:
    job = get_job(owner_id, lecture_id, job_id)
    if job is None:
        raise ValueError("job not found or not owned")
    update = {"stage": stage.value, "updated_at": _now()}
    if timings:
        update["timings"] = {**job.timings, **timings}
    job_ref(lecture_id, job_id).update(update)


def fail_job(
    owner_id: str, lecture_id: str, job_id: str, code: ErrorCode, message: str
) -> None:
    job = get_job(owner_id, lecture_id, job_id)
    if job is None:
        return
    job_ref(lecture_id, job_id).update(
        {
            "state": "failed",
            "stage": JobStage.FAILED.value,
            "safe_error_code": code.value,
            "safe_error_message": message,
            "updated_at": _now(),
        }
    )
