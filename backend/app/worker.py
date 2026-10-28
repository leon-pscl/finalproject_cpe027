"""Background pipeline worker: queued upload -> media/DSP -> ASR.

It runs from the FastAPI lifespan so a local instance processes uploads without a
separate process. The repository and storage are the same instances the API uses
(both resolve through app.dependencies), a claim lease is renewed by a heartbeat
while media and ASR run, and the stage, DSP timings and a transcript artifact are
written back so the result stays retrievable.
"""

from __future__ import annotations

import json
import logging
import tempfile
import threading
import uuid
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.adapters import adapter_bundle
from app.asr import Transcript, transcribe_file

from app.config import Settings
from app.contracts import ErrorCode, JobStage, LectureMetadata, LectureStatus
from app.media import DSPConfig, LocalMediaService
from app.repositories import LectureRepository
from app.storage import LocalStorageAdapter, StorageAdapter

logger = logging.getLogger(__name__)

POLL_SECONDS = 1.0
# A CPU Whisper run on a long lecture takes minutes, so the lease is long and is
# renewed well before it expires.
LEASE_SECONDS = 600
HEARTBEAT_SECONDS = LEASE_SECONDS // 3

Transcriber = Callable[..., Transcript]


class PipelineWorker:
    def __init__(
        self,
        repository: LectureRepository,
        storage: StorageAdapter,
        settings: Settings,
        *,
        transcriber: Transcriber | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.settings = settings
        self._transcriber = transcriber
        self.worker_id = worker_id or f"local-{uuid.uuid4().hex[:8]}"
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run_forever(self) -> None:
        while not self._stop.is_set():
            if not self.run_once():
                self._stop.wait(POLL_SECONDS)

    def run_once(self) -> bool:
        """Claim and process one queued job; return True when a job was handled."""
        # ponytail: FirestoreLectureRepository.list_all_lectures() returns [], so a
        # Firestore deployment needs a queued-jobs query here instead of this scan.
        for lecture in self.repository.list_all_lectures():
            for job in self.repository.list_jobs(lecture_id=lecture.lecture_id):
                if not self.repository.claim_job(
                    lecture.owner_id,
                    lecture.lecture_id,
                    job.job_id,
                    self.worker_id,
                    lease_seconds=LEASE_SECONDS,
                ):
                    continue
                self._process(lecture.owner_id, lecture.lecture_id, job.job_id)
                return True
        return False

    def _stage(
        self, owner_id: str, lecture_id: str, job_id: str, stage: JobStage
    ) -> None:
        self.repository.update_job_stage(owner_id, lecture_id, job_id, stage)

    def _process(self, owner_id: str, lecture_id: str, job_id: str) -> None:
        stop_beat = threading.Event()
        beat = threading.Thread(
            target=self._heartbeat,
            args=(owner_id, lecture_id, job_id, stop_beat),
            name=f"heartbeat-{job_id}",
            daemon=True,
        )
        beat.start()
        timings: dict[str, Any] = {}
        try:
            lecture = self.repository.get_lecture(owner_id, lecture_id)
            if lecture is None:
                raise LookupError("lecture was removed before processing")
            self._stage(owner_id, lecture_id, job_id, JobStage.VALIDATING)
            # LocalMediaService fuses ffmpeg extraction with every DSP stage, so the
            # whole unit is reported as preprocessing; its per-stage runtimes land
            # in timings["dsp"] below.
            self._stage(owner_id, lecture_id, job_id, JobStage.PREPROCESSING)
            media = self._run_media(lecture, timings)
            self._stage(owner_id, lecture_id, job_id, JobStage.TRANSCRIBING)
            # media.py already ran the DSP pass, so ASR must never enhance again.
            transcript = (self._transcriber or transcribe_file)(
                media["audio_asset"]["dsp_path"], enhance=False
            )
            timings["asr"] = {
                "provider": "faster-whisper",
                "model": self.settings.whisper_model,
                "language": transcript.language,
                "duration": round(transcript.duration, 3),
                "segments": len(transcript.segments),
                "completed_at": datetime.now(UTC).isoformat(timespec="seconds"),
            }
                            self._save_artifact(owner_id, lecture_id, transcript)

                # Indexing stage: chunk and embed the transcript.
                self._stage(owner_id, lecture_id, job_id, JobStage.INDEXING)
                adapters = adapter_bundle()
                chunker = adapters["chunker"]
                embedder = adapters["embedder"]
                # Chunking
                chunk_start = time.monotonic()
                config = {"lecture_id": lecture_id, "version": "v1"}
                chunks = chunker.chunk(transcript.segments, config)
                timings["chunking"] = round(time.monotonic() - chunk_start, 4)
                # Embedding
                embed_start = time.monotonic()
                vectors = embedder.embed([c.text for c in chunks], config)
                timings["embedding"] = round(time.monotonic() - embed_start, 4)
                # Combine chunks with embeddings for storage.
                enriched_chunks = []
                for chunk, vec in zip(chunks, vectors):
                    chunk_dict = chunk.dict()
                    chunk_dict["embedding"] = vec
                    enriched_chunks.append(chunk_dict)
                # Save enriched chunks JSON.
                self.storage.save_object(
                    f"users/{owner_id}/{lecture_id}/chunks.json",
                    json.dumps(enriched_chunks, indent=2).encode("utf-8"),
                    "application/json",
                )
            self.repository.update_job_state(
                owner_id,
                lecture_id,
                job_id,
                state="completed",
                stage=JobStage.COMPLETED,
                timings=timings,
            )
            self.repository.mark_lecture_state(
                owner_id, lecture_id, LectureStatus.COMPLETED
            )
            logger.info(
                "job %s completed with %s segments", job_id, len(transcript.segments)
            )
        except Exception as exc:  # any failure must fail the job
            logger.exception("job %s failed", job_id)
            self.repository.update_job_state(
                owner_id, lecture_id, job_id, timings=timings
            )
            # The client gets a stable code and a generic message; the detail stays
            # in the log so stored paths never reach the response.
            self.repository.fail_job(
                owner_id,
                lecture_id,
                job_id,
                ErrorCode.PROCESSING_FAILED,
                f"Processing failed ({type(exc).__name__})",
            )
            self.repository.mark_lecture_state(
                owner_id, lecture_id, LectureStatus.FAILED
            )
        finally:
            stop_beat.set()
            beat.join(timeout=HEARTBEAT_SECONDS + 1)

    def _heartbeat(
        self, owner_id: str, lecture_id: str, job_id: str, stop: threading.Event
    ) -> None:
        while not stop.wait(HEARTBEAT_SECONDS):
            renewed = self.repository.heartbeat_job(
                owner_id,
                lecture_id,
                job_id,
                self.worker_id,
                lease_seconds=LEASE_SECONDS,
            )
            if not renewed:
                logger.warning("lease for job %s was lost", job_id)
                return

    def _run_media(
        self, lecture: LectureMetadata, timings: dict[str, Any]
    ) -> dict[str, Any]:
        service = LocalMediaService(self.settings)
        temporary: Path | None = None
        if isinstance(self.storage, LocalStorageAdapter):
            media_kwargs: dict[str, Any] = {
                "storage_root": self.settings.local_storage_root,
                "storage_path": lecture.storage_path,
            }
        else:
            # Remote object storage: materialize the object, then discard it.
            data, _ = self.storage.read_object(lecture.storage_path)
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=Path(lecture.storage_path).suffix
            ) as handle:
                handle.write(data)
            temporary = Path(handle.name)
            media_kwargs = {"source_path": temporary}
        try:
            media = service.validate_and_extract(
                owner_id=lecture.owner_id,
                lecture_id=lecture.lecture_id,
                **media_kwargs,
            )
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        timings["dsp"] = {
            "enabled": media["dsp_enabled"],
            "configuration": asdict(DSPConfig.from_settings(self.settings)),
            "stage_runtimes": media["stage_runtimes"],
            "diagnostics": media["diagnostics"],
        }
        return media

    def _save_artifact(
        self, owner_id: str, lecture_id: str, transcript: Transcript
    ) -> None:
        payload = {
            "language": transcript.language,
            "duration": transcript.duration,
            "segments": [asdict(segment) for segment in transcript.segments],
        }
        self.storage.save_object(
            f"users/{owner_id}/{lecture_id}/transcript.json",
            json.dumps(payload, indent=2).encode("utf-8"),
            "application/json",
        )
