import json
import logging
import os
import tempfile
import threading
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.asr import Transcript
from app.chunker import Chunker
from app.contracts import AnswerResponse, Chunk, ErrorCode, NoteEntry, ProcessingOptions
from app.embedder import Embedder
from app.routers import delete, dsp, lectures, notes, qa, storage

from .config import get_settings
from .processing_profile import resolve_from_mapping
from .dependencies import get_repository, get_storage
from .jobs import JobStore
from .processing_profile import resolve_from_mapping
from .worker import PipelineWorker

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mp4", ".webm", ".ogg", ".flac"}
CHUNK = 1024 * 1024


@asynccontextmanager
async def lifespan(instance: FastAPI):
    """Run the upload pipeline worker for the lifetime of the app."""
    settings = get_settings()
    if settings.processing_mode == "real":
        missing = []

        if not settings.groq_api_key:
            missing.append("GROQ_API_KEY")
        if missing:
            logger.warning("Real mode enabled but missing provider keys: %s", ", ".join(missing))

    if not settings.worker_enabled:
        logger.info("pipeline worker disabled (set WORKER_ENABLED=true to enable)")
        yield
        return
    worker = PipelineWorker(get_repository(settings), get_storage(settings), settings)
    thread = threading.Thread(
        target=worker.run_forever, name="pipeline-worker", daemon=True
    )
    instance.state.worker = worker
    instance.state.worker_thread = thread
    thread.start()
    logger.info("pipeline worker started (worker_id=%s)", worker.worker_id)
    try:
        yield
    finally:
        worker.stop()
        thread.join(timeout=5)


app = FastAPI(
    title="LectureFlow API",
    description="Lecture transcription API (pretrained faster-whisper).",
    version="0.3.0",
    lifespan=lifespan,
)

try:
    _settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, str(_settings.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
except Exception:
    pass


@lru_cache
def get_store() -> JobStore:
    return JobStore()


class SegmentOut(BaseModel):
    id: str
    start: float
    end: float
    text: str
    confidence: float


class JobOut(BaseModel):
    id: str
    status: Literal["queued", "processing", "completed", "failed"]
    progress: float
    language: str | None = None
    duration: float = 0.0
    segments: list[SegmentOut] = []
    error: str | None = None
    phase: str = "queued"
    dsp: dict | None = None
    dsp_url: str | None = None


def _to_out(job) -> JobOut:
    return JobOut(
        id=job.id,
        status=job.status,
        progress=round(job.progress, 3),
        language=job.language,
        duration=job.duration,
        segments=[SegmentOut(**vars(s)) for s in list(job.segments)],
        error=job.error,
        phase=job.phase,
        dsp=job.dsp,
        dsp_url=job.dsp.get('signed_url') if isinstance(job.dsp, dict) else None,
    )


@app.get("/api/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "lectureflow-backend"}


app.include_router(lectures.router, prefix="/api")
app.include_router(storage.router, prefix="/api")
app.include_router(notes.router, prefix="/api")
app.include_router(dsp.router, prefix="/api")
app.include_router(delete.router, prefix="/api")
app.include_router(qa.router, prefix="/api")





@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    messages = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error.get("loc", []))
        if location:
            messages.append(f"{location}: {error.get('msg', 'invalid value')}")
        else:
            messages.append(str(error.get("msg", "invalid request")))
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "error_code": ErrorCode.INVALID_REQUEST.value,
                "message": "; ".join(messages),
            }
        },
    )


@app.post(
    "/api/transcriptions",
    status_code=202,
    response_model=JobOut,
    tags=["transcription"],
)
async def create_transcription(
    file: UploadFile = File(...),  # noqa: B008
    enhance: bool | None = Form(None),
    processing_options: str | None = Form(None),
    store: JobStore = Depends(get_store),  # noqa: B008
) -> JobOut:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, f"Unsupported file type '{ext}'. Use WAV, MP3 or M4A.")

    request_options = None
    if processing_options:
        try:
            request_options = json.loads(processing_options)
        except (json.JSONDecodeError, TypeError) as exc:
            raise HTTPException(422, f"Invalid processing options: {exc}") from exc
        if not isinstance(request_options, dict):
            raise HTTPException(422, "Processing options must be a JSON object")

    settings = get_settings()
    if enhance is True:
        request_options = dict(request_options or {})
        request_options["requested_legacy_enhance"] = True

    try:
        resolved = resolve_from_mapping(settings, request_options)
    except ValueError as exc:
        raise HTTPException(422, f"Invalid or unauthorized processing options: {exc}") from exc

    options_payload = resolved.options.model_dump()
    options_payload["requested_legacy_enhance"] = bool(enhance)

    limit = settings.max_upload_mb * CHUNK
    size = 0
    fd, path = tempfile.mkstemp(suffix=ext, prefix="lecture-")
    try:
        with os.fdopen(fd, "wb") as out:
            while chunk := await file.read(CHUNK):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(
                        413,
                        f"File exceeds the {get_settings().max_upload_mb} MB limit.",
                    )
                out.write(chunk)
        if size == 0:
            raise HTTPException(400, "The uploaded file is empty.")
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise

    return _to_out(store.submit(path, enhance=enhance, processing_options=options_payload))


@app.get("/api/transcriptions/{job_id}", response_model=JobOut, tags=["transcription"])
def get_transcription(job_id: str, store: JobStore = Depends(get_store)) -> JobOut:  # noqa: B008
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, "Transcription not found.")
    return _to_out(job)


@app.get("/api/transcriptions/{job_id}/audio", tags=["transcription"])
def get_transcription_audio(job_id: str, store: JobStore = Depends(get_store)) -> FileResponse:  # noqa: B008
    job = store.get(job_id)
    if job is None or not getattr(job, "dsp_audio_path", None):
        raise HTTPException(404, "Processed audio not found.")
    from pathlib import Path as _Path

    path = _Path(job.dsp_audio_path)
    if not path.is_file():
        raise HTTPException(404, "Processed audio not found.")
    return FileResponse(path, media_type="audio/wav", filename=f"dsp-{job_id}.wav")


@app.post("/api/transcriptions/{job_id}/notes", response_model=list[NoteEntry], tags=["transcription"])
def generate_transcription_notes(job_id: str, store: JobStore = Depends(get_store)) -> list[NoteEntry]:  # noqa: B008
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, "Transcription not found.")
    if job.status != "completed":
        raise HTTPException(409, "Transcription is not complete.")

    from app.adapters import adapter_bundle
    from app.vector_store import FAISSVectorStore

    settings = get_settings()
    transcript = Transcript(
        language=job.language, duration=job.duration, segments=list(job.segments)
    )
    chunks = Chunker().chunk(transcript, job.id, "v1")
    if chunks:
        vectors = Embedder().embed(chunks)
        FAISSVectorStore(settings.local_storage_root, job.id).add(
            [chunk.model_dump() for chunk in chunks], vectors
        )
    notes_gen = adapter_bundle()["notes"]
    return notes_gen.generate(
        chunks, {"lecture_id": job.id, "processing_version": "v1"}
    ) or []


class TranscriptionAnswerRequest(BaseModel):
    question: str
    top_k: int = 5


@app.post("/api/transcriptions/{job_id}/answer", response_model=AnswerResponse, tags=["transcription"])
def generate_transcription_answer(
    job_id: str,
    request: TranscriptionAnswerRequest,
    store: JobStore = Depends(get_store),
) -> AnswerResponse:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, "Transcription not found.")
    if job.status != "completed":
        raise HTTPException(409, "Transcription is not complete.")

    from app.adapters import adapter_bundle
    from app.embedder import Embedder
    from app.vector_store import FAISSVectorStore

    settings = get_settings()
    transcript = Transcript(
        language=job.language, duration=job.duration, segments=list(job.segments)
    )
    chunks = Chunker().chunk(transcript, job.id, "v1")
    if chunks:
        vectors = Embedder().embed(chunks)
        FAISSVectorStore(settings.local_storage_root, job.id).add(
            [chunk.model_dump() for chunk in chunks], vectors
        )

    vector_store = FAISSVectorStore(settings.local_storage_root, job.id)
    if vector_store.index is not None:
        tmp = Chunk(
            chunk_id="tmp",
            lecture_id=job.id,
            version="v1",
            segment_ids=[],
            start_s=0.0,
            end_s=0.0,
            text=request.question,
            embedding_model="tmp",
            embedding_revision="0",
        )
        query_vec = Embedder().embed([tmp])[0]
        top_chunks = [Chunk(**chunk) for chunk, _ in vector_store.query(query_vec, top_k=request.top_k)]
    else:
        top_chunks = chunks

    answer_gen = adapter_bundle()["answer"]
    return answer_gen.answer(
        request.question,
        top_chunks,
        {"lecture_id": job.id, "processing_version": "v1"},
    )


@app.delete("/api/transcriptions/{job_id}", status_code=204, tags=["transcription"])
def delete_transcription(job_id: str, store: JobStore = Depends(get_store)) -> None:  # noqa: B008
    store.delete(job_id)
