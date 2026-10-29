import logging
import os
import tempfile
import threading
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.contracts import ErrorCode
from app.routers import lectures, storage, qa, notes, export, delete, dsp


from .config import get_settings
from .dependencies import get_repository, get_storage
from .jobs import JobStore
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
        if not settings.openai_api_key:
            missing.append("OPENAI_API_KEY")
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
    store: JobStore = Depends(get_store),  # noqa: B008
) -> JobOut:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, f"Unsupported file type '{ext}'. Use WAV, MP3 or M4A.")

    limit = get_settings().max_upload_mb * CHUNK
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
    return _to_out(store.submit(path, enhance=enhance))


@app.get("/api/transcriptions/{job_id}", response_model=JobOut, tags=["transcription"])
def get_transcription(job_id: str, store: JobStore = Depends(get_store)) -> JobOut:  # noqa: B008
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, "Transcription not found.")
    return _to_out(job)


@app.delete("/api/transcriptions/{job_id}", status_code=204, tags=["transcription"])
def delete_transcription(job_id: str, store: JobStore = Depends(get_store)) -> None:  # noqa: B008
    store.delete(job_id)
