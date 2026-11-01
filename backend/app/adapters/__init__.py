"""Adapter selection – always use real adapters (no mock mode)."""

from __future__ import annotations

from typing import Any

# Import only the real adapters.
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

# Single adapter map.
_ADAPTERS: dict[str, dict[str, type[Any]]] = {
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
    """Instantiate adapters – real implementations."""
    classes = _ADAPTERS["real"]
    return {name: cls() for name, cls in classes.items()}
