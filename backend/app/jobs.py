"""Background transcription jobs (in-process queue; Redis + RQ replaces this in a later step)."""

from __future__ import annotations

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

    def submit(self, path: str, enhance: bool | None = None) -> Job:
        self._expire()
        job = Job(id=uuid.uuid4().hex, path=path, enhance=enhance)
        with self._lock:
            self._jobs[job.id] = job
        self._pool.submit(self._run, job.id)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def delete(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.pop(job_id, None)
        if job and job.path:
            _remove(job.path)
        if job and job.dsp_audio_path:
            _remove(job.dsp_audio_path)
        return job is not None

    def _run(self, job_id: str) -> None:
        job = self.get(job_id)
        if job is None:  # deleted while queued
            return
        job.status = "processing"
        job.phase = "enhancing"

        def on_progress(p: float) -> None:
            job.progress = p

        def on_segment(seg: Segment) -> None:
            job.segments.append(seg)

        def on_phase(name: str) -> None:
            job.phase = name

        try:
            audio_dir = os.path.join(get_settings().local_storage_root, "asr-dsp")
            os.makedirs(audio_dir, exist_ok=True)
            audio_path = os.path.join(audio_dir, f"{job.id}.wav")
            from . import dsp

            settings = get_settings()
            enhance = job.enhance if job.enhance is not None else True
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
                    on_progress=(lambda p: on_progress(0.1 * p)) if on_progress else None,
                )
                dsp.write_wav(audio_path, enhanced)
                job.dsp = report.as_dict() if hasattr(report, "as_dict") else report
            except Exception as exc:  # noqa: BLE001 - DSP should never prevent transcription itself
                job.dsp = {"applied": False, "error": f"{type(exc).__name__}: {exc}"}
                try:
                    dsp.write_wav(audio_path, dsp.load_audio(job.path))
                except Exception:
                    audio_path = None
            job.dsp_audio_path = audio_path if audio_path and os.path.exists(audio_path) else None
            if job.dsp_audio_path:
                (job.dsp if isinstance(job.dsp, dict) else {}).setdefault("audio_path", job.dsp_audio_path)
                (job.dsp if isinstance(job.dsp, dict) else {}).setdefault("signed_url", f"/api/transcriptions/{job.id}/audio")

            audio_for_asr = job.dsp_audio_path or job.path
            result = self._transcriber(
                audio_for_asr,
                on_progress=on_progress,
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
        except Exception as exc:  # noqa: BLE001 - surfaced to the client, not swallowed
            job.error, job.status = f"{type(exc).__name__}: {exc}", "failed"
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


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
