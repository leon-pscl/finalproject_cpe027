"""Background transcription jobs (in-process queue; Redis + RQ replaces this in a later step)."""
from __future__ import annotations

import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Optional

from .asr import Segment, Transcript, transcribe_file
from .config import get_settings

Transcriber = Callable[..., Transcript]


@dataclass
class Job:
    id: str
    status: str = "queued"  # queued | processing | completed | failed
    progress: float = 0.0
    language: Optional[str] = None
    duration: float = 0.0
    segments: list[Segment] = field(default_factory=list)
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    path: Optional[str] = None
    enhance: Optional[bool] = None
    phase: str = "queued"  # queued | enhancing | transcribing | done
    dsp: Optional[dict] = None


class JobStore:
    def __init__(self, transcriber: Transcriber = transcribe_file, workers: Optional[int] = None):
        self._transcriber = transcriber
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=workers or get_settings().workers)

    def submit(self, path: str, enhance: Optional[bool] = None) -> Job:
        self._expire()
        job = Job(id=uuid.uuid4().hex, path=path, enhance=enhance)
        with self._lock:
            self._jobs[job.id] = job
        self._pool.submit(self._run, job.id)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def delete(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.pop(job_id, None)
        if job and job.path:
            _remove(job.path)
        return job is not None

    def _run(self, job_id: str) -> None:
        job = self.get(job_id)
        if job is None:  # deleted while queued
            return
        job.status = "processing"

        def on_progress(p: float) -> None:
            job.progress = p

        def on_segment(seg: Segment) -> None:
            job.segments.append(seg)

        def on_phase(name: str) -> None:
            job.phase = name

        try:
            result = self._transcriber(
                job.path, on_progress=on_progress, on_segment=on_segment, on_phase=on_phase, enhance=job.enhance
            )
            job.dsp = result.dsp
            job.language, job.duration = result.language, result.duration
            job.progress, job.status, job.phase = 1.0, "completed", "done"
        except Exception as exc:  # surfaced to the client, not swallowed
            job.error, job.status = f"{type(exc).__name__}: {exc}", "failed"
        finally:
            # The browser keeps its own copy; the server does not retain raw audio after processing.
            if job.path:
                _remove(job.path)
                job.path = None

    def _expire(self) -> None:
        cutoff = time.time() - get_settings().job_ttl_seconds
        with self._lock:
            stale = [j for j in self._jobs.values() if j.created_at < cutoff and j.status in ("completed", "failed")]
            for j in stale:
                self._jobs.pop(j.id, None)


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
