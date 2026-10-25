"""Tests use stub transcribers/models (test-only) so no model weights are needed."""

import io
import os
import time
from types import SimpleNamespace

import pytest
from app import asr, main
from app.asr import Segment, Transcript
from app.jobs import JobStore
from fastapi.testclient import TestClient


def fake_transcriber(path, on_progress=None, on_segment=None, **_):
    assert os.path.exists(path)
    seg = Segment("seg-1", 1.0, 4.5, "hello lecture", 0.9)
    on_segment(seg)
    on_progress(0.5)
    return Transcript(language="en", duration=10.0, segments=[seg])


def failing_transcriber(path, **_):
    raise RuntimeError("decode failed")


def make_client(transcriber):
    store = JobStore(transcriber=transcriber, workers=1)
    main.app.dependency_overrides[main.get_store] = lambda: store
    return TestClient(main.app), store


@pytest.fixture(autouse=True)
def _reset():
    yield
    main.app.dependency_overrides.clear()


def wait_done(client, job_id, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        body = client.get(f"/api/transcriptions/{job_id}").json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def upload(client, name="lecture.wav", data=b"RIFFxxxx"):
    return client.post(
        "/api/transcriptions", files={"file": (name, io.BytesIO(data), "audio/wav")}
    )


def test_upload_transcribes_and_returns_segments():
    client, _ = make_client(fake_transcriber)
    res = upload(client)
    assert res.status_code == 202
    body = wait_done(client, res.json()["id"])
    assert body["status"] == "completed"
    assert body["language"] == "en" and body["duration"] == 10.0
    assert body["segments"] == [
        {
            "id": "seg-1",
            "start": 1.0,
            "end": 4.5,
            "text": "hello lecture",
            "confidence": 0.9,
        }
    ]


def test_raw_audio_is_removed_after_processing():
    paths = []

    def spy(path, **kw):
        paths.append(path)
        return fake_transcriber(path, **kw)

    client, _ = make_client(spy)
    wait_done(client, upload(client).json()["id"])
    time.sleep(0.05)
    assert paths and not os.path.exists(paths[0])


def test_failure_is_reported_not_hidden():
    client, _ = make_client(failing_transcriber)
    body = wait_done(client, upload(client).json()["id"])
    assert body["status"] == "failed" and "decode failed" in body["error"]


def test_rejects_unsupported_and_empty_files():
    client, _ = make_client(fake_transcriber)
    assert upload(client, name="notes.txt").status_code == 415
    assert upload(client, data=b"").status_code == 400


def test_unknown_and_deleted_jobs_return_404():
    client, _ = make_client(fake_transcriber)
    assert client.get("/api/transcriptions/nope").status_code == 404
    job_id = upload(client).json()["id"]
    wait_done(client, job_id)
    assert client.delete(f"/api/transcriptions/{job_id}").status_code == 204
    assert client.get(f"/api/transcriptions/{job_id}").status_code == 404


def test_transcribe_file_maps_model_output_and_drops_non_speech():
    raw = [
        SimpleNamespace(
            start=0.0,
            end=3.0,
            text=" Noise reduction. ",
            avg_logprob=-0.1,
            no_speech_prob=0.01,
        ),
        SimpleNamespace(
            start=3.0, end=5.0, text="   ", avg_logprob=-0.2, no_speech_prob=0.0
        ),
        SimpleNamespace(
            start=5.0, end=8.0, text="music", avg_logprob=-0.5, no_speech_prob=0.95
        ),
        SimpleNamespace(
            start=8.0,
            end=10.0,
            text="STFT uses windows.",
            avg_logprob=-1.2,
            no_speech_prob=0.1,
        ),
    ]
    seen = {}

    class StubModel:
        def transcribe(self, path, **kwargs):
            seen.update(kwargs)
            return iter(raw), SimpleNamespace(language="en", duration=10.0)

    progress = []
    out = asr.transcribe_file(
        "x.wav",
        on_progress=progress.append,
        glossary=["STFT", "ASR"],
        model=StubModel(),
        enhance=False,
    )
    assert [s.text for s in out.segments] == ["Noise reduction.", "STFT uses windows."]
    assert out.segments[0].confidence == pytest.approx(0.905, abs=0.001)
    assert out.segments[1].confidence < out.segments[0].confidence
    assert seen["vad_filter"] is True and seen["initial_prompt"] == "STFT, ASR"
    assert progress[-1] <= 0.99
