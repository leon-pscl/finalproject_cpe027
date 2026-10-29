"""Adapter selection by validated configuration (never by UI code)."""

from __future__ import annotations

from typing import Any

from app.adapters.mock import (
    MockAnswerGenerator,
    MockAudioProcessor,
    MockChunker,
    MockEmbedder,
    MockMediaService,
    MockNotesGenerator,
    MockRetriever,
    MockTranscriber,
)
from app.adapters.real import (
    RealAnswerGenerator,
    RealAudioProcessor,
    RealChunker,
    RealEmbedder,
    RealMediaService,
    RealNotesGenerator,
    RealRetriever,
    RealTranscriber,
)
from app.config import get_settings

_ADAPTERS: dict[str, dict[str, type[Any]]] = {
    "mock": {
        "media": MockMediaService,
        "audio": MockAudioProcessor,
        "transcriber": MockTranscriber,
        "chunker": MockChunker,
        "embedder": MockEmbedder,
        "retriever": MockRetriever,
        "answer": MockAnswerGenerator,
        "notes": MockNotesGenerator,
    },
    "real": {
        "media": RealMediaService,
        "audio": RealAudioProcessor,
        "transcriber": RealTranscriber,
        "chunker": RealChunker,
        "embedder": RealEmbedder,
        "retriever": RealRetriever,
        "answer": RealAnswerGenerator,
        "notes": RealNotesGenerator,
    },
}


def adapter_bundle() -> dict[str, Any]:
    """Instantiate adapters according to validated settings."""
    mode = get_settings().processing_mode
    classes = _ADAPTERS[mode]
    return {name: cls() for name, cls in classes.items()}
