"""Shared API and processing contracts.

These are the stable shapes exchanged between the frontend, API, worker, and
tests. Keep identifiers opaque; derive ownership from the verified token uid.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    AUTH_REQUIRED = "AUTH_REQUIRED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    AUTH_INVALID = "AUTH_INVALID"
    INVALID_REQUEST = "INVALID_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    FORBIDDEN = "FORBIDDEN"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    UNSUPPORTED_FILE = "UNSUPPORTED_FILE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    DURATION_TOO_LONG = "DURATION_TOO_LONG"
    STORED_OBJECT_MISMATCH = "STORED_OBJECT_MISMATCH"
    JOB_ALREADY_ACTIVE = "JOB_ALREADY_ACTIVE"
    JOB_NOT_RETRYABLE = "JOB_NOT_RETRYABLE"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    INVALID_CITATION = "INVALID_CITATION"
    ADAPTER_NOT_CONFIGURED = "ADAPTER_NOT_CONFIGURED"


class ErrorResponse(BaseModel):
    error_code: ErrorCode
    message: str
    request_id: str | None = None


class JobStage(str, Enum):
    QUEUED = "queued"
    VALIDATING = "validating"
    EXTRACTING = "extracting"
    PREPROCESSING = "preprocessing"
    TRANSCRIBING = "transcribing"
    INDEXING = "indexing"
    GENERATING_NOTES = "generating_notes"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


JobState = Literal["queued", "running", "completed", "failed", "cancelled"]


class LectureStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TranscriptSegment(BaseModel):
    segment_id: str
    lecture_id: str
    version: str
    order: int
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    text: str
    diagnostic_flags: list[str] = Field(default_factory=list)


class Chunk(BaseModel):
    chunk_id: str
    lecture_id: str
    version: str
    segment_ids: list[str]
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    text: str
    embedding: list[float] | None = None
    embedding_model: str | None = None
    embedding_revision: str | None = None


class SourceReference(BaseModel):
    source_id: str
    segment_id: str | None = None
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    text: str


class AnswerBlock(BaseModel):
    block_id: str
    text: str
    source_ids: list[str] = Field(default_factory=list)


class AnswerStatus(str, Enum):
    ANSWERED = "answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    ERROR = "error"


class AnswerResponse(BaseModel):
    answer_id: str
    lecture_id: str
    version: str
    processing_mode: str
    status: AnswerStatus
    blocks: list[AnswerBlock] = Field(default_factory=list)
    sources: list[SourceReference] = Field(default_factory=list)


class UploadInitiationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    declared_type: str = Field(min_length=1, max_length=128)
    declared_size_bytes: int = Field(gt=0)


class UploadInitiationResponse(BaseModel):
    lecture_id: str
    storage_path: str
    signed_upload_url: str
    expires_at: datetime


class UploadCompleteRequest(BaseModel):
    storage_path: str
    observed_size_bytes: int | None = None
    observed_content_type: str | None = None


class UploadCompleteResponse(BaseModel):
    lecture_id: str
    job_id: str
    stage: JobStage = JobStage.QUEUED
    message: str = "queued"


class LectureMetadata(BaseModel):
    lecture_id: str
    owner_id: str
    title: str
    storage_path: str
    duration_s: float | None = None
    media_metadata: dict = Field(default_factory=dict)
    state: LectureStatus = LectureStatus.PENDING
    active_version: str | None = None
    deleted_at: datetime | None = None
    created_at: datetime


class JobDocument(BaseModel):
    job_id: str
    lecture_id: str
    processing_version: str
    stage: JobStage = JobStage.QUEUED
    state: JobState = "queued"
    attempts: int = 0
    lease_until: datetime | None = None
    worker_id: str | None = None
    safe_error_code: ErrorCode | None = None
    timings: dict = Field(default_factory=dict)


class NoteEntry(BaseModel):
    note_id: str
    lecture_id: str
    version: str
    section: str
    title: str
    description: str
    supporting_segment_ids: list[str] = Field(default_factory=list)


class ExportFormat(str, Enum):
    TXT = "txt"
    VTT = "vtt"
    MARKDOWN = "md"
