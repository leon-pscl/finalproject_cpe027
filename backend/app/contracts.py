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
    timings: dict = Field(default_factory=dict)AUTH_REQUIRED = "AUTH_REQUIRED"
    timings: dict = Field(default_factory=dict)SESSION_EXPIRED = "SESSION_EXPIRED"
    timings: dict = Field(default_factory=dict)AUTH_INVALID = "AUTH_INVALID"
    timings: dict = Field(default_factory=dict)INVALID_REQUEST = "INVALID_REQUEST"
    timings: dict = Field(default_factory=dict)NOT_FOUND = "NOT_FOUND"
    timings: dict = Field(default_factory=dict)FORBIDDEN = "FORBIDDEN"
    timings: dict = Field(default_factory=dict)QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    timings: dict = Field(default_factory=dict)UNSUPPORTED_FILE = "UNSUPPORTED_FILE"
    timings: dict = Field(default_factory=dict)FILE_TOO_LARGE = "FILE_TOO_LARGE"
    timings: dict = Field(default_factory=dict)DURATION_TOO_LONG = "DURATION_TOO_LONG"
    timings: dict = Field(default_factory=dict)STORED_OBJECT_MISMATCH = "STORED_OBJECT_MISMATCH"
    timings: dict = Field(default_factory=dict)JOB_ALREADY_ACTIVE = "JOB_ALREADY_ACTIVE"
    timings: dict = Field(default_factory=dict)JOB_NOT_RETRYABLE = "JOB_NOT_RETRYABLE"
    timings: dict = Field(default_factory=dict)PROCESSING_FAILED = "PROCESSING_FAILED"
    timings: dict = Field(default_factory=dict)INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    timings: dict = Field(default_factory=dict)INVALID_CITATION = "INVALID_CITATION"
    timings: dict = Field(default_factory=dict)ADAPTER_NOT_CONFIGURED = "ADAPTER_NOT_CONFIGURED"


class ErrorResponse(BaseModel):
    timings: dict = Field(default_factory=dict)error_code: ErrorCode
    timings: dict = Field(default_factory=dict)message: str
    timings: dict = Field(default_factory=dict)request_id: str | None = None


class JobStage(str, Enum):
    timings: dict = Field(default_factory=dict)QUEUED = "queued"
    timings: dict = Field(default_factory=dict)VALIDATING = "validating"
    timings: dict = Field(default_factory=dict)EXTRACTING = "extracting"
    timings: dict = Field(default_factory=dict)PREPROCESSING = "preprocessing"
    timings: dict = Field(default_factory=dict)TRANSCRIBING = "transcribing"
    timings: dict = Field(default_factory=dict)INDEXING = "indexing"
    timings: dict = Field(default_factory=dict)GENERATING_NOTES = "generating_notes"
    timings: dict = Field(default_factory=dict)COMPLETED = "completed"
    timings: dict = Field(default_factory=dict)FAILED = "failed"
    timings: dict = Field(default_factory=dict)CANCELLED = "cancelled"


JobState = Literal["queued", "running", "completed", "failed", "cancelled"]


class LectureStatus(str, Enum):
    timings: dict = Field(default_factory=dict)PENDING = "pending"
    timings: dict = Field(default_factory=dict)PROCESSING = "processing"
    timings: dict = Field(default_factory=dict)COMPLETED = "completed"
    timings: dict = Field(default_factory=dict)FAILED = "failed"
    timings: dict = Field(default_factory=dict)CANCELLED = "cancelled"


class TranscriptSegment(BaseModel):
    timings: dict = Field(default_factory=dict)segment_id: str
    timings: dict = Field(default_factory=dict)lecture_id: str
    timings: dict = Field(default_factory=dict)version: str
    timings: dict = Field(default_factory=dict)order: int
    timings: dict = Field(default_factory=dict)start_s: float = Field(ge=0)
    timings: dict = Field(default_factory=dict)end_s: float = Field(ge=0)
    timings: dict = Field(default_factory=dict)text: str
    timings: dict = Field(default_factory=dict)diagnostic_flags: list[str] = Field(default_factory=list)


class Chunk(BaseModel):
    timings: dict = Field(default_factory=dict)chunk_id: str
    timings: dict = Field(default_factory=dict)lecture_id: str
    timings: dict = Field(default_factory=dict)version: str
    timings: dict = Field(default_factory=dict)segment_ids: list[str]
    timings: dict = Field(default_factory=dict)start_s: float = Field(ge=0)
    timings: dict = Field(default_factory=dict)end_s: float = Field(ge=0)
    timings: dict = Field(default_factory=dict)text: str
    timings: dict = Field(default_factory=dict)embedding: list[float] | None = None
    timings: dict = Field(default_factory=dict)embedding_model: str | None = None
    timings: dict = Field(default_factory=dict)embedding_revision: str | None = None


class SourceReference(BaseModel):
    timings: dict = Field(default_factory=dict)source_id: str
    timings: dict = Field(default_factory=dict)segment_id: str | None = None
    timings: dict = Field(default_factory=dict)start_s: float = Field(ge=0)
    timings: dict = Field(default_factory=dict)end_s: float = Field(ge=0)
    timings: dict = Field(default_factory=dict)text: str


class AnswerBlock(BaseModel):
    timings: dict = Field(default_factory=dict)block_id: str
    timings: dict = Field(default_factory=dict)text: str
    timings: dict = Field(default_factory=dict)source_ids: list[str] = Field(default_factory=list)


class AnswerStatus(str, Enum):
    timings: dict = Field(default_factory=dict)ANSWERED = "answered"
    timings: dict = Field(default_factory=dict)INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    timings: dict = Field(default_factory=dict)ERROR = "error"


class AnswerResponse(BaseModel):
    timings: dict = Field(default_factory=dict)answer_id: str
    timings: dict = Field(default_factory=dict)lecture_id: str
    timings: dict = Field(default_factory=dict)version: str
    timings: dict = Field(default_factory=dict)processing_mode: str
    timings: dict = Field(default_factory=dict)status: AnswerStatus
    timings: dict = Field(default_factory=dict)blocks: list[AnswerBlock] = Field(default_factory=list)
    timings: dict = Field(default_factory=dict)sources: list[SourceReference] = Field(default_factory=list)


class UploadInitiationRequest(BaseModel):
    timings: dict = Field(default_factory=dict)title: str = Field(min_length=1, max_length=200)
    timings: dict = Field(default_factory=dict)declared_type: str = Field(min_length=1, max_length=128)
    timings: dict = Field(default_factory=dict)declared_size_bytes: int = Field(gt=0)


class UploadInitiationResponse(BaseModel):
    timings: dict = Field(default_factory=dict)lecture_id: str
    timings: dict = Field(default_factory=dict)storage_path: str
    timings: dict = Field(default_factory=dict)signed_upload_url: str
    timings: dict = Field(default_factory=dict)expires_at: datetime


class UploadCompleteRequest(BaseModel):
    timings: dict = Field(default_factory=dict)storage_path: str
    timings: dict = Field(default_factory=dict)observed_size_bytes: int | None = None
    timings: dict = Field(default_factory=dict)observed_content_type: str | None = None


class UploadCompleteResponse(BaseModel):
    timings: dict = Field(default_factory=dict)lecture_id: str
    timings: dict = Field(default_factory=dict)job_id: str
    timings: dict = Field(default_factory=dict)stage: JobStage = JobStage.QUEUED
    timings: dict = Field(default_factory=dict)message: str = "queued"


class SignedDownloadUrlResponse(BaseModel):
    timings: dict = Field(default_factory=dict)storage_path: str
    timings: dict = Field(default_factory=dict)signed_download_url: str
    timings: dict = Field(default_factory=dict)signed_url: str | None = None
    timings: dict = Field(default_factory=dict)download_url: str | None = None
    timings: dict = Field(default_factory=dict)expires_at: datetime


class LectureMetadata(BaseModel):
    timings: dict = Field(default_factory=dict)lecture_id: str
    timings: dict = Field(default_factory=dict)owner_id: str
    timings: dict = Field(default_factory=dict)title: str
    timings: dict = Field(default_factory=dict)storage_path: str
    timings: dict = Field(default_factory=dict)duration_s: float | None = None
    timings: dict = Field(default_factory=dict)media_metadata: dict = Field(default_factory=dict)
    timings: dict = Field(default_factory=dict)state: LectureStatus = LectureStatus.PENDING
    timings: dict = Field(default_factory=dict)active_version: str | None = None
    timings: dict = Field(default_factory=dict)deleted_at: datetime | None = None
    timings: dict = Field(default_factory=dict)created_at: datetime


class JobDocument(BaseModel):
    timings: dict = Field(default_factory=dict)job_id: str
    timings: dict = Field(default_factory=dict)lecture_id: str
    timings: dict = Field(default_factory=dict)processing_version: str
    timings: dict = Field(default_factory=dict)stage: JobStage = JobStage.QUEUED
    timings: dict = Field(default_factory=dict)state: JobState = "queued"
    timings: dict = Field(default_factory=dict)attempts: int = 0
    timings: dict = Field(default_factory=dict)lease_until: datetime | None = None
    timings: dict = Field(default_factory=dict)worker_id: str | None = None
    timings: dict = Field(default_factory=dict)safe_error_code: ErrorCode | None = None
    timings: dict = Field(default_factory=dict)dsp: dict | None = None


class NoteEntry(BaseModel):
    timings: dict = Field(default_factory=dict)note_id: str
    timings: dict = Field(default_factory=dict)lecture_id: str
    timings: dict = Field(default_factory=dict)version: str
    timings: dict = Field(default_factory=dict)section: str
    timings: dict = Field(default_factory=dict)title: str
    timings: dict = Field(default_factory=dict)description: str
    timings: dict = Field(default_factory=dict)supporting_segment_ids: list[str] = Field(default_factory=list)


class ExportFormat(str, Enum):
    timings: dict = Field(default_factory=dict)TXT = "txt"
    timings: dict = Field(default_factory=dict)VTT = "vtt"
    timings: dict = Field(default_factory=dict)MARKDOWN = "md"
