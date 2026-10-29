"""Background pipeline worker: queued upload -> media/DSP -> ASR.

It runs from the FastAPI lifespan so a local instance processes uploads without a
separate process. The repository and storage are the same instances the API uses
(both resolve through app.dependencies), a claim lease is renewed by a heartbeat
while media and ASR run, and the stage, DSP timings and a transcript artifact are
written back so the result stays retrievable.
"""

from __future__ import annotations

import json
from .vector_store import FAISSVectorStore
import logging

logger = logging.getLogger(__name__)

import tempfile
import wave
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
                # Process the claimed job
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
            job = self.repository.get_job(owner_id, lecture_id, job_id)
            if lecture is None:
                raise LookupError("lecture was removed before processing")
                self._stage(owner_id, lecture_id, job_id, JobStage.VALIDATING)
                logger.info("Stage %s for job %s", JobStage.VALIDATING, job_id)

            # LocalMediaService fuses ffmpeg extraction with every DSP stage, so the
            # whole unit is reported as preprocessing; its per-stage runtimes land
            # in timings["dsp"] below.
            self._stage(owner_id, lecture_id, job_id, JobStage.PREPROCESSING)
            logger.info("Stage %s for job %s", JobStage.PREPROCESSING, job_id)

            media = self._run_media(lecture, timings)
            # Store DSP‑enhanced audio for streaming via signed URL
            dsp_local_path = media["audio_asset"]["dsp_path"]
            dsp_storage_path = f"users/{owner_id}/{lecture_id}/dsp.wav"
            try:
                with open(dsp_local_path, "rb") as f:
                    dsp_data = f.read()
                self.storage.save_object(dsp_storage_path, dsp_data, "audio/wav")
                # Create signed URL for the stored DSP audio
                signed_url, _ = self.storage.create_signed_download_url(dsp_storage_path, expires_in_minutes=15)
                job.dsp = {"signed_url": signed_url, **(job.dsp or {})}
            except Exception as exc:
                logger.warning("Failed to store DSP audio or create signed URL: %s", exc)
            self._stage(owner_id, lecture_id, job_id, JobStage.TRANSCRIBING)
            logger.info("Stage %s for job %s", JobStage.TRANSCRIBING, job_id)

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
            logger.info("Stage %s for job %s", JobStage.INDEXING, job_id)

            adapters = adapter_bundle()
            chunker = adapters["chunker"]
            embedder = adapters["embedder"]
            # Chunking
            chunk_start = time.monotonic()
            config = {"lecture_id": lecture_id, "version": "v1"}
            chunks = chunker.chunk(transcript, config)
            timings["chunking"] = round(time.monotonic() - chunk_start, 4)
            # Embedding
            embed_start = time.monotonic()
            vectors = embedder.embed(chunks)
            timings["embedding"] = round(time.monotonic() - embed_start, 4)
            # Combine chunks with embeddings for storage.
            enriched_chunks = []
            for chunk, vec in zip(chunks, vectors):
                chunk_dict = chunk.dict()
                chunk_dict["embedding"] = vec
                enriched_chunks.append(chunk_dict)
            # Save enriched chunks JSON.
            # Save enriched chunks JSON for backward‑compatibility.
            self.storage.save_object(
                f"users/{owner_id}/{lecture_id}/chunks.json",
                json.dumps(enriched_chunks, indent=2).encode("utf-8"),
                "application/json",
            )
            # Persist vectors and metadata to FAISS on disk.
            faiss_store = FAISSVectorStore(self.settings.local_storage_root, lecture_id)
            faiss_store.add(enriched_chunks, vectors)


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
        # Mock processing mode skips heavy ffmpeg/ffprobe calls.
        if self.settings.processing_mode != "real":
            # Resolve source file path for local storage.
            if isinstance(self.storage, LocalStorageAdapter):
                source_path = Path(self.settings.local_storage_root) / lecture.storage_path
            else:
                data, _ = self.storage.read_object(lecture.storage_path)
                temporary = Path(tempfile.NamedTemporaryFile(delete=False, suffix=Path(lecture.storage_path).suffix).name)
                temporary.write_bytes(data)
                source_path = temporary
            # Compute duration using wave module when possible.
            try:
                with wave.open(str(source_path), "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    duration = frames / float(rate) if rate else 0.0
            except Exception:
                duration = None
            # Copy source to a dummy DSP file with dsp_ prefix to satisfy naming expectations.
            dsp_temp = Path(tempfile.NamedTemporaryFile(delete=False, prefix="dsp_", suffix=Path(lecture.storage_path).suffix).name)
            dsp_temp.write_bytes(source_path.read_bytes())
            dsp_path = dsp_temp

            audio_asset = {
                "type": "local",
                "path": str(source_path),
                "arm_a_path": str(source_path),
                "dsp_path": str(dsp_path),
                "duration_s": duration,
                "format": "audio/wav",
                "sample_format": "pcm_f32le",
            }
            media = {
                "audio_asset": audio_asset,
                "diagnostics": {"probe": {"duration_seconds": duration} if duration is not None else {}},
                "stage_runtimes": {"high_pass": 0.0, "spectral_gating": 0.0, "normalization": 0.0, "vad": 0.0, "dsp_total": 0.0},
                "dsp_enabled": self.settings.dsp_enabled,
            }
        else:
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
