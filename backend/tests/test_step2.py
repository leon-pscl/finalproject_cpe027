"""Tests for Step 2 upload, queue, ownership, and quota behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import VerifiedUser
from app.config import clear_settings_cache, get_settings
from app.dependencies import clear_repository_cache, get_current_user
from app.main import app
from app.repositories import InMemoryLectureRepository, deterministic_job_id


@pytest.fixture
def step2_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPOSITORY_BACKEND", "memory")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path / "storage"))
    clear_settings_cache()
    clear_repository_cache()
    settings = get_settings()
    settings.local_storage_root = str(tmp_path / "storage")
    yield
    app.dependency_overrides.clear()
    clear_repository_cache()
    clear_settings_cache()


@pytest.fixture
def authorized_client(step2_env: None):
    current = {"uid": "user-a"}

    def _user():
        return VerifiedUser(uid=current["uid"])

    app.dependency_overrides[get_current_user] = _user
    client = TestClient(app)
    yield client, current


def _initiate_upload(
    client: TestClient, title: str = "Lecture"
) -> tuple[str, str, str]:
    response = client.post(
        "/api/lectures/uploads",
        json={"title": title, "declared_type": "video/mp4", "declared_size_bytes": 24},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return body["lecture_id"], body["storage_path"], body["signed_upload_url"]


def _store_upload(client: TestClient, signed_url: str, size: int = 24) -> None:
    response = client.put(
        signed_url,
        content=b"x" * size,
        headers={"content-type": "video/mp4"},
    )
    assert response.status_code == 200, response.text


def test_repeated_upload_complete_creates_one_job(authorized_client):
    client, _ = authorized_client
    lecture_id, storage_path, signed_url = _initiate_upload(client)
    _store_upload(client, signed_url)

    first = client.post(
        f"/api/lectures/{lecture_id}/upload-complete",
        json={"storage_path": storage_path},
    )
    assert first.status_code == 202
    assert first.json()["stage"] == "queued"
    first_job = first.json()["job_id"]

    second = client.post(
        f"/api/lectures/{lecture_id}/upload-complete",
        json={"storage_path": storage_path},
    )
    assert second.status_code == 202
    assert second.json()["job_id"] == first_job
    assert second.json()["stage"] == "queued"


def test_cross_user_isolation(step2_env: None):
    current = {"uid": "user-a"}

    def _user():
        return VerifiedUser(uid=current["uid"])

    app.dependency_overrides[get_current_user] = _user
    with TestClient(app) as client_a:
        lecture_id, _, _ = _initiate_upload(client_a, "User A")

    with TestClient(app) as client_b:
        current["uid"] = "user-b"
        response = client_b.get(f"/api/lectures/{lecture_id}")
        assert response.status_code == 404
        assert response.json()["detail"]["error_code"] == "NOT_FOUND"
        listing = client_b.get("/api/lectures")
        assert listing.status_code == 200
        assert all(item["lecture_id"] != lecture_id for item in listing.json())


def test_lease_recovery():
    owner = "owner"
    lecture_id = "lecture-1"
    processing_version = "v1"
    job_id = deterministic_job_id(lecture_id, processing_version)
    repository = InMemoryLectureRepository()
    repository.create_lecture(owner, lecture_id, "Lecture", "path", "video/mp4", 10)
    repository.create_job(owner, lecture_id, job_id, processing_version)

    assert repository.claim_job(owner, lecture_id, job_id, "worker-a")
    expired = datetime.now(UTC) - timedelta(seconds=60)
    repository.update_job_state(owner, lecture_id, job_id, lease_until=expired)

    assert repository.claim_job(owner, lecture_id, job_id, "worker-b")
    job = repository.get_job(owner, lecture_id, job_id)
    assert job is not None
    assert job.state == "running"
    assert job.worker_id == "worker-b"
    assert job.attempts == 2


def test_over_limit_rejection(step2_env: None, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PER_USER_DAILY_JOB_LIMIT", "1")
    clear_settings_cache()
    clear_repository_cache()
    settings = get_settings()
    settings.per_user_daily_job_limit = 1

    current = {"uid": "user-a"}

    def _user():
        return VerifiedUser(uid=current["uid"])

    app.dependency_overrides[get_current_user] = _user
    with TestClient(app) as client:
        first_id, first_path, first_url = _initiate_upload(client, "First")
        _store_upload(client, first_url)
        first_response = client.post(
            f"/api/lectures/{first_id}/upload-complete",
            json={"storage_path": first_path},
        )
        assert first_response.status_code == 202

        second_id, second_path, second_url = _initiate_upload(client, "Second")
        _store_upload(client, second_url)
        rejected = client.post(
            f"/api/lectures/{second_id}/upload-complete",
            json={"storage_path": second_path},
        )
        assert rejected.status_code == 429
        assert rejected.json()["detail"]["error_code"] == "QUOTA_EXCEEDED"
