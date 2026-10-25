"""Real adapter stubs.

In safe local mode these raise immediately when invoked. They are only selected
when ``PROCESSING_MODE=real`` and the relevant provider is configured.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.adapters.base import (
    AnswerGenerator,
    AudioProcessor,
    Chunker,
    Embedder,
    MediaService,
    NotesGenerator,
    Retriever,
    Transcriber,
)
from app.config import get_settings


# Local error type kept here so the module imports without depending on contracts.
class AdapterNotConfigured(RuntimeError):
    """Raised when a real adapter is selected but its provider is not configured."""


def _require_real_mode(name: str) -> None:
    settings = get_settings()
    if settings.processing_mode != "real":
        raise AdapterNotConfigured(f"{name} requires PROCESSING_MODE=real")
    raise AdapterNotConfigured(
        f"{name} is selected in real mode but no provider implementation is "
        "configured in this build; implement the provider adapter first."
    )


class RealMediaService(MediaService):
    def validate_and_extract(self, lecture_id: str, processing_version: str) -> dict:
        _require_real_mode("RealMediaService")
        return {}


class RealAudioProcessor(AudioProcessor):
    def process(self, audio_asset: Any, config: dict) -> Any:
        _require_real_mode("RealAudioProcessor")


class RealTranscriber(Transcriber):
    def transcribe(self, audio_asset: Any, config: dict) -> list[Any]:
        _require_real_mode("RealTranscriber")
        return []


class RealChunker(Chunker):
    def chunk(self, timed_segments: Sequence[Any], config: dict) -> list[Any]:
        _require_real_mode("RealChunker")
        return []


class RealEmbedder(Embedder):
    def embed(self, texts: Sequence[str], config: dict) -> list[list[float]]:
        _require_real_mode("RealEmbedder")
        return []


class RealRetriever(Retriever):
    def search(
        self, owner_id: str, lecture_id: str, processing_version: str, question: str
    ) -> list[Any]:
        _require_real_mode("RealRetriever")
        return []


class RealAnswerGenerator(AnswerGenerator):
    def answer(
        self, question: str, authorized_evidence: Sequence[Any], config: dict
    ) -> Any:
        _require_real_mode("RealAnswerGenerator")


class RealNotesGenerator(NotesGenerator):
    def generate(
        self, authorized_timed_chunks: Sequence[Any], config: dict
    ) -> list[Any]:
        _require_real_mode("RealNotesGenerator")
        return []
