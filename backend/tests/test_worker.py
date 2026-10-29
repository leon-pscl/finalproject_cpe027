"""Tests for the upload -> media/DSP -> ASR pipeline worker."""

from __future__ import annotations

import json
import math
import time
import wave
from array import array
from pathlib import Path

import pytest
from app.asr import Segment, Transcript
from app.auth import VerifiedUser
from app.config import Settings, clear_settings_cache
from app.contracts import ErrorCode, JobStage, LectureStatus
from app.dependencies import clear_repository_cache, get_current_user
from app.main import app
from app.repositories import (
    InMemoryLectureRepository,
    deterministic_job_id,
)
from app.storage import LocalStorageAdapter
from app.worker import PipelineWorker
from fastapi.testclient import TestClient

OWNER = "user-a"
LECTURE = "lecture-1"
JOB = deterministic_job_id(LECTURE, "v1")
SOURCE_REL = f"users/{OWNER}/{LECTURE}/source.wav"
ARTIFACT_REL = f"users/{OWNER}/{LECTURE}/transcript.json"


class RecordingTranscriber:
    """Stands in for asr.transcribe_file and records how it was called."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, path: str, **kwargs) -> Transcript:
        self.calls.append((path, kwargs))
        return Transcript(
            language="en",
            duration=0.5,
            segments=[Segment("seg-1", 0.0, 0.5, "hello", 0.9)],
        )


def _write_tone_wav(path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = array(
        "h",
        (int(4000 * math.sin(2 * math.pi * 220 * i / 16000)) for i in range(8000)),
    )
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(samples.tobytes())
    return path.stat().st_size


def _pipeline(tmp_path: Path, *, dsp_enabled: bool):
    storage_root = tmp_path / "storage"
    settings = Settings(
        _env_file=None,
        repository_backend="memory",
        local_storage_root=str(storage_root),
        dsp_enabled=dsp_enabled,
    )
    repository = InMemoryLectureRepository()
    storage = LocalStorageAdapter(settings)
    transcriber = RecordingTranscriber()
    worker = PipelineWorker(repository, storage, settings, transcriber=transcriber)
    return repository, storage, worker, transcriber, settings


def _seed(repository: InMemoryLectureRepository, storage_path: str, size: int) -> None:
    repository.create_lecture(
        OWNER, LECTURE, "Lecture", storage_path, "audio/wav", size
    )
    repository.create_job(OWNER, LECTURE, JOB, "v1")


def test_worker_completes_upload_and_records_one_dsp_pass(tmp_path: Path) -> None:
    repository, storage, worker, transcriber, settings = _pipeline(
        tmp_path, dsp_enabled=False
    )
    _seed(repository, SOURCE_REL, _write_tone_wav(tmp_path / "storage" / SOURCE_REL))

    assert worker.run_once() is True

    job = repository.get_job(OWNER, LECTURE, JOB)
    assert job is not None
    assert job.state == "completed"
    assert job.stage == JobStage.COMPLETED
    lecture = repository.get_lecture(OWNER, LECTURE)
    assert lecture is not None and lecture.state == LectureStatus.COMPLETED

    # media.py already ran the DSP pass: ASR receives the processed file and is
    # told not to enhance again, so there is exactly one pass.
    path, kwargs = transcriber.calls[0]
    assert kwargs["enhance"] is False
    assert Path(path).name.startswith("dsp_")

    dsp = job.timings["dsp"]
    assert dsp["enabled"] is False
    assert dsp["configuration"]["bypass"] is True
    assert dsp["stage_runtimes"]["high_pass"] == 0.0
    assert dsp["diagnostics"]["probe"]["duration_seconds"] > 0

    assert job.timings["asr"]["model"] == settings.whisper_model
    assert job.timings["asr"]["segments"] == 1

    blob, content_type = storage.read_object(ARTIFACT_REL)
    payload = json.loads(blob)
    assert content_type == "application/json"
    assert payload["segments"][0]["text"] == "hello"


def test_worker_runs_dsp_stages_when_enabled(tmp_path: Path) -> None:
    repository, _, worker, transcriber, _ = _pipeline(tmp_path, dsp_enabled=True)
    _seed(repository, SOURCE_REL, _write_tone_wav(tmp_path / "storage" / SOURCE_REL))

    assert worker.run_once() is True

    job = repository.get_job(OWNER, LECTURE, JOB)
    assert job is not None and job.state == "completed"
    assert transcriber.calls[0][1]["enhance"] is False

    dsp = job.timings["dsp"]
    assert dsp["enabled"] is True
    assert dsp["configuration"]["bypass"] is False
    assert dsp["configuration"]["high_pass_cutoff_hz"] == 80.0
    assert dsp["stage_runtimes"]["dsp_total"] > 0.0


def test_worker_fails_job_when_media_is_missing(tmp_path: Path) -> None:
    repository, _, worker, transcriber, _ = _pipeline(tmp_path, dsp_enabled=False)
    _seed(repository, f"users/{OWNER}/{LECTURE}/missing.wav", 10)

    assert worker.run_once() is True

    job = repository.get_job(OWNER, LECTURE, JOB)
    assert job is not None
    assert job.state == "failed"
    assert job.stage == JobStage.FAILED
    assert job.safe_error_code == ErrorCode.PROCESSING_FAILED
    lecture = repository.get_lecture(OWNER, LECTURE)
    assert lecture is not None and lecture.state == LectureStatus.FAILED
    assert transcriber.calls == []


def test_run_once_returns_false_when_queue_is_empty(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        repository_backend="memory",
        local_storage_root=str(tmp_path / "storage"),
    )
    worker = PipelineWorker(
        InMemoryLectureRepository(), LocalStorageAdapter(settings), settings
    )
    assert worker.run_once() is False


def test_lifespan_gate_starts_and_stops_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WORKER_ENABLED", "true")
    monkeypatch.setenv("REPOSITORY_BACKEND", "memory")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path / "storage"))
    clear_settings_cache()
    clear_repository_cache()
    try:
        with TestClient(app) as client:
            assert client.get("/api/health").status_code == 200
            worker = app.state.worker
            thread = app.state.worker_thread
            assert worker is not None
            assert thread.is_alive()
        assert not thread.is_alive()
    finally:
        clear_settings_cache()
        clear_repository_cache()


def test_api_upload_reaches_the_lifespan_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End to end: a job created through the API must reach the worker's repository."""
    monkeypatch.setenv("WORKER_ENABLED", "true")
    monkeypatch.setenv("REPOSITORY_BACKEND", "memory")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path / "storage"))
    clear_settings_cache()
    clear_repository_cache()
    app.dependency_overrides[get_current_user] = lambda: VerifiedUser(uid=OWNER)
    try:
        with TestClient(app) as client:
            initiated = client.post(
                "/api/lectures/uploads",
                json={
                    "title": "Lecture",
                    "declared_type": "video/mp4",
                    "declared_size_bytes": 12,
                },
            )
            assert initiated.status_code == 200, initiated.text
            lecture_id = initiated.json()["lecture_id"]
            stored = client.put(
                initiated.json()["signed_upload_url"],
                content=b"x" * 12,
                headers={"content-type": "video/mp4"},
            )
            assert stored.status_code == 200, stored.text
            queued = client.post(
                f"/api/lectures/{lecture_id}/upload-complete",
                json={"storage_path": initiated.json()["storage_path"]},
            )
            assert queued.status_code == 202, queued.text
            assert queued.json()["stage"] == "queued"

            # The worker claims the queued job and fails on undecodable media.
            state = "queued"
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                state = client.get(f"/api/lectures/{lecture_id}").json()["state"]
                if state == "failed":
                    break
                time.sleep(0.5)
            assert state == "failed"
    finally:
        app.dependency_overrides.clear()
        clear_settings_cache()
        clear_repository_cache()
