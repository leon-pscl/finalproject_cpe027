<<<<<<< HEAD
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.contracts import ErrorCode
from app.routers import lectures, storage
=======
import os
import tempfile
from functools import lru_cache
from typing import Literal, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .config import get_settings
from .jobs import JobStore

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mp4", ".webm", ".ogg", ".flac"}
CHUNK = 1024 * 1024
>>>>>>> iteration_lim

app = FastAPI(
    title="LectureFlow API",
    description="Lecture transcription API (pretrained faster-whisper).",
    version="0.3.0",
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
    language: Optional[str] = None
    duration: float = 0.0
    segments: list[SegmentOut] = []
    error: Optional[str] = None
    phase: str = "queued"
    dsp: Optional[dict] = None


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
    )


@app.get("/api/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "lectureflow-backend"}


<<<<<<< HEAD
app.include_router(lectures.router, prefix="/api")
app.include_router(storage.router, prefix="/api")


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
=======
@app.post("/api/transcriptions", status_code=202, response_model=JobOut, tags=["transcription"])
async def create_transcription(
    file: UploadFile = File(...), enhance: Optional[bool] = Form(None), store: JobStore = Depends(get_store)
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
                    raise HTTPException(413, f"File exceeds the {get_settings().max_upload_mb} MB limit.")
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
def get_transcription(job_id: str, store: JobStore = Depends(get_store)) -> JobOut:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, "Transcription not found.")
    return _to_out(job)


@app.delete("/api/transcriptions/{job_id}", status_code=204, tags=["transcription"])
def delete_transcription(job_id: str, store: JobStore = Depends(get_store)) -> None:
    store.delete(job_id)
>>>>>>> iteration_lim
