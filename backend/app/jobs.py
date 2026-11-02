"""Background transcription jobs (in-process queue; Redis + RQ replaces this in a later step)."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .asr import Segment, Transcript, transcribe_file
from .config import get_settings

Transcriber = Callable[..., Transcript]


@dataclass
class Job:
    id: str
    status: str = "queued"  # queued | processing | completed | failed
    progress: float = 0.0
    language: str | None = None
    duration: float = 0.0
    segments: list[Segment] = field(default_factory=list)
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    path: str | None = None
    enhance: bool | None = None
    phase: str = "queued"  # queued | enhancing | transcribing | done
    dsp: dict | None = None
    dsp_audio_path: str | None = None


class JobStore:
    def __init__(
        self, transcriber: Transcriber = transcribe_file, workers: int | None = None
    ):
        self._transcriber = transcriber
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=workers or get_settings().workers)
        self._storage_root = os.path.abspath(get_settings().local_storage_root)
        self._jobs_dir = os.path.join(self._storage_root, "jobs")
        os.makedirs(self._jobs_dir, exist_ok=True)

    def submit(self, path: str, enhance: bool | None = None) -> Job:
        self._expire()
        job = Job(id=uuid.uuid4().hex, path=path, enhance=enhance)
        with self._lock:
            self._jobs[job.id] = job
        self._persist_job(job)
        self._pool.submit(self._run, job.id)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                return job
        persisted = self._read_job(job_id)
        if persisted is not None:
            # A persisted queued/processing record whose worker stopped updating is
            # a dead/interrupted process, not a live job: surface that instead of 404.
            if persisted.status in ("queued", "processing"):
                age = time.time() - (persisted.updated_at or persisted.created_at)
                if age > 600:
                    persisted.status = "failed"
                    persisted.phase = "failed"
                    persisted.error = (
                        persisted.error
                        or "Transcription did not finish (processing was interrupted)."
                    )
                    persisted.updated_at = time.time()
                    self._persist_job(persisted)
            with self._lock:
                self._jobs[job_id] = persisted
            return persisted
        return None

    def delete(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.pop(job_id, None)
        if job is None:
            job = self._read_job(job_id)
        existed = job is not None
        if job and job.path:
            _remove(job.path)
        if job and job.dsp_audio_path:
            _remove(job.dsp_audio_path)
        try:
            os.remove(self._job_file(job_id))
        except FileNotFoundError:
            pass
        return existed

    def _job_file(self, job_id: str) -> str:
        safe = job_id.replace("/", "").replace("\\", "")
        return os.path.join(self._jobs_dir, f"{safe}.json")

    def _persist_job(self, job: Job) -> None:
        try:
            payload = {
                "id": job.id,
                "status": job.status,
                "progress": job.progress,
                "language": job.language,
                "duration": job.duration,
                "segments": [vars(s) for s in list(job.segments)],
                "error": job.error,
                "created_at": job.created_at,
                "updated_at": job.updated_at,
                "path": None,
                "enhance": job.enhance,
                "phase": job.phase,
                "dsp": job.dsp,
                "dsp_audio_path": job.dsp_audio_path,
            }
            with open(self._job_file(job.id), "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, allow_nan=False)
        except (OSError, TypeError, ValueError):
            pass

    def _read_job(self, job_id: str) -> Job | None:
        path = self._job_file(job_id)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None
        try:
            created_at = float(payload.get("created_at", time.time()))
        except (TypeError, ValueError):
            created_at = time.time()
        try:
            updated_at = float(payload.get("updated_at", created_at))
        except (TypeError, ValueError):
            updated_at = created_at
        if created_at < time.time() - get_settings().job_ttl_seconds:
            try:
                os.remove(path)
            except OSError:
                pass
            return None
        job = Job(
            id=str(payload.get("id") or job_id),
            status=str(payload.get("status", "failed")),
            progress=float(payload.get("progress", 0.0) or 0.0),
            language=payload.get("language"),
            duration=float(payload.get("duration", 0.0) or 0.0),
            segments=[
                Segment(
                    id=str(item.get("id", "seg")),
                    start=float(item.get("start", 0.0) or 0.0),
                    end=float(item.get("end", 0.0) or 0.0),
                    text=str(item.get("text", "")),
                    confidence=float(item.get("confidence", 0.0) or 0.0),
                )
                for item in payload.get("segments") or []
            ],
            error=payload.get("error"),
            created_at=created_at,
            updated_at=updated_at,
            path=None,
            enhance=payload.get("enhance"),
            phase=str(payload.get("phase", payload.get("status", "failed"))),
            dsp=payload.get("dsp"),
            dsp_audio_path=payload.get("dsp_audio_path"),
        )
        return job

    def _run(self, job_id: str) -> None:
        job = self.get(job_id)
        if job is None:  # deleted while queued
            return
        job.status = "processing"
        job.phase = "enhancing"
        job.updated_at = time.time()
        self._persist_job(job)

        def on_progress(p: float) -> None:
            job.progress = p
            job.updated_at = time.time()
            last = getattr(job, "_last_persist", 0.0)
            if time.time() - last >= 5:
                job._last_persist = time.time()
                self._persist_job(job)

        def on_segment(seg: Segment) -> None:
            job.segments.append(seg)
            job.updated_at = time.time()
            if len(job.segments) % 5 == 0 or len(job.segments) == 1:
                self._persist_job(job)

        def on_phase(name: str) -> None:
            job.phase = name
            job.updated_at = time.time()
            self._persist_job(job)

        # Preflight: fail clearly when a file is longer than the configured max,
        # instead of disappearing mid-run.
        try:
            from pathlib import Path

            from .media import probe_media

            info = probe_media(Path(job.path)) if job.path else None
            settings = get_settings()
            if (
                info is not None
                and info.duration_seconds is not None
                and info.duration_seconds > settings.max_duration_minutes * 60
            ):
                raise ValueError(
                    f"media duration {int(info.duration_seconds)}s exceeds the configured maximum "
                    f"of {settings.max_duration_minutes} minutes"
                )
        except Exception as exc:  # noqa: BLE001 - ignore probe failures (e.g. test media)
            if "exceeds the configured maximum" in str(exc):
                job.error = f"{type(exc).__name__}: {exc}"
                job.status = "failed"
                job.phase = "failed"
                job.updated_at = time.time()
                self._persist_job(job)
                return

        try:
            from . import dsp

            settings = get_settings()
            audio_dir = os.path.join(settings.local_storage_root, "asr-dsp")
            os.makedirs(audio_dir, exist_ok=True)
            audio_path = os.path.join(audio_dir, f"{job.id}.wav")
            try:
                x = dsp.load_audio(job.path)
                enhanced, report = dsp.enhance(
                    x,
                    method=getattr(settings, "dsp_method", "wiener"),
                    rt60=float(settings.dsp_rt60),
                    floor_db=float(settings.dsp_floor_db),
                    reverb_weight=float(settings.dsp_reverb_weight),
                    noise_bias=float(settings.dsp_noise_bias),
                    use_vad_held=getattr(settings, "dsp_use_vad_held", True),
                    on_progress=(lambda p: on_progress(0.1 * p))
                    if on_progress
                    else None,
                )
                dsp.write_wav(audio_path, enhanced)
                job.dsp = report.as_dict() if hasattr(report, "as_dict") else report
            except Exception as exc:  # noqa: BLE001 - DSP should never prevent transcription itself
                job.dsp = {"applied": False, "error": f"{type(exc).__name__}: {exc}"}
                try:
                    dsp.write_wav(audio_path, dsp.load_audio(job.path))
                except Exception:  # noqa: BLE001
                    audio_path = None
            job.dsp_audio_path = (
                audio_path if audio_path and os.path.exists(audio_path) else None
            )
            if job.dsp_audio_path:
                (job.dsp if isinstance(job.dsp, dict) else {}).setdefault(
                    "audio_path", job.dsp_audio_path
                )
                (job.dsp if isinstance(job.dsp, dict) else {}).setdefault(
                    "signed_url", f"/api/transcriptions/{job.id}/audio"
                )
            job.updated_at = time.time()
            self._persist_job(job)

            audio_for_asr = job.dsp_audio_path or job.path
            logger = logging.getLogger(__name__)
            logger.info("Starting ASR transcription for %s", audio_for_asr)
            # Continue progress monotonically from the DSP stage (0.1 -> 1.0),
            # rather than letting ASR restart the bar at zero.
            job.progress = max(job.progress, 0.1)
            job.phase = "transcribing"
            job.updated_at = time.time()
            self._persist_job(job)

            def on_asr_progress(p: float) -> None:
                try:
                    value = 0.1 + 0.9 * float(p)
                except (TypeError, ValueError):
                    value = 0.1
                job.progress = max(job.progress, min(0.999, value))
                job.updated_at = time.time()
                last = getattr(job, "_last_persist", 0.0)
                if time.time() - last >= 5:
                    job._last_persist = time.time()
                    self._persist_job(job)

            result = self._transcriber(
                audio_for_asr,
                on_progress=on_asr_progress,
                on_segment=on_segment,
                on_phase=on_phase,
                enhance=False,
            )
            if isinstance(job.dsp, dict) and isinstance(result.dsp, dict):
                result.dsp.update(job.dsp)
            elif isinstance(job.dsp, dict):
                result.dsp = job.dsp
            job.language, job.duration = result.language, result.duration
            job.progress, job.status, job.phase = 1.0, "completed", "done"
            job.updated_at = time.time()
            job.segments = list(result.segments)
            self._persist_job(job)
        except Exception as exc:  # noqa: BLE001 - surfaced to the client, not swallowed
            job.error, job.status = f"{type(exc).__name__}: {exc}", "failed"
            job.phase = "failed"
            job.updated_at = time.time()
            self._persist_job(job)
        finally:
            # The browser keeps its own copy; the server does not retain raw audio after processing.
            if job.path:
                _remove(job.path)
                job.path = None

    def _expire(self) -> None:
        cutoff = time.time() - get_settings().job_ttl_seconds
        with self._lock:
            stale = [
                j
                for j in self._jobs.values()
                if j.created_at < cutoff and j.status in ("completed", "failed")
            ]
            for j in stale:
                self._jobs.pop(j.id, None)
        try:
            for name in os.listdir(self._jobs_dir):
                if not name.endswith(".json"):
                    continue
                path = os.path.join(self._jobs_dir, name)
                try:
                    with open(path, "r", encoding="utf-8") as handle:
                        payload = json.load(handle)
                    created_at = float(payload.get("created_at", time.time()))
                    if created_at < cutoff and payload.get("status") in (
                        "completed",
                        "failed",
                    ):
                        os.remove(path)
                except (OSError, json.JSONDecodeError, TypeError, ValueError):
                    continue
        except OSError:
            pass


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
