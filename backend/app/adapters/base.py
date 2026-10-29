"""Stable adapter interfaces for the processing pipeline."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from app.contracts import AnswerResponse, Chunk, NoteEntry, TranscriptSegment


class MediaService(Protocol):
    def validate_and_extract(
        self, lecture_id: str, processing_version: str
    ) -> dict[str, Any]: ...


class AudioProcessor(Protocol):
    def process(self, audio_asset: Any, config: dict[str, Any]) -> Any: ...


class Transcriber(Protocol):
    def transcribe(
        self, audio_asset: Any, config: dict[str, Any]
    ) -> list[TranscriptSegment]: ...


class Chunker(Protocol):
    def chunk(
        self, timed_segments: Sequence[TranscriptSegment], config: dict[str, Any]
    ) -> list[Chunk]: ...


class Embedder(Protocol):
    def embed(
        self, texts: Sequence[str], config: dict[str, Any]
    ) -> list[list[float]]: ...


class Retriever(Protocol):
    def search(
        self,
        owner_id: str,
        lecture_id: str,
        processing_version: str,
        question: str,
    ) -> list[Chunk]: ...


class AnswerGenerator(Protocol):
    def answer(
        self,
        question: str,
        authorized_evidence: Sequence[Chunk],
        config: dict[str, Any],
    ) -> AnswerResponse: ...


class NotesGenerator(Protocol):
    def generate(
        self, authorized_timed_chunks: Sequence[Chunk], config: dict[str, Any]
    ) -> list[NoteEntry]: ...
