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
# Import concrete implementations for real mode delegation
from app.chunker import Chunker as ChunkerImpl
from app.embedder import Embedder as EmbedderImpl
from app.asr import Transcript


from app.config import get_settings

class AdapterNotConfigured(RuntimeError):
    """Raised when a real adapter is selected but its provider is not configured."""
    pass


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
        """Delegate to concrete Chunker implementation.

        `timed_segments` are the ASR Segment objects. We build a Transcript and
        invoke the shared Chunker, which respects config settings for chunk size
        and overlap.
        """
        # Compute total duration from segment end times.
        duration = max((seg.end for seg in timed_segments), default=0.0)
        # Build a Transcript compatible with the Chunker implementation.
        transcript = Transcript(language="en", duration=duration, segments=list(timed_segments))
        chunker = ChunkerImpl()
        return chunker.chunk(
            transcript,
            config.get("lecture_id", ""),
            config.get("version", ""),
        )



class RealEmbedder(Embedder):
    def embed(self, texts: Sequence[str], config: dict) -> list[list[float]]:
        # `texts` corresponds to the chunk texts. We'll construct dummy Chunk
        # objects just to satisfy the shared Embedder implementation, which expects
        # a list of `Chunk` instances with a `text` attribute.
        from ..contracts import Chunk as ChunkModel
        dummy_chunks = [ChunkModel(chunk_id="tmp", lecture_id=config.get("lecture_id", ""), version=config.get("version", ""), segment_ids=[], start_s=0.0, end_s=0.0, text=t, embedding_model="", embedding_revision="") for t in texts]
        embedder = EmbedderImpl()
        return embedder.embed(dummy_chunks)



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
        # Summarize lecture using OpenAI LLM. Concatenate chunk texts and ask for a short
        # summary (max ~300 words). This mirrors the mock behavior but produces a real note.
        from app.answer_generator import OpenAIAnswerGenerator

        # Build a simple context from all chunk texts.
        context = " ".join(c.get("text", "") for c in authorized_timed_chunks)
        prompt = (
            "Summarize the following lecture content in up to 300 words. "
            "Focus on the main topics, important facts, and any conclusions."
        )
        answer_gen = OpenAIAnswerGenerator()
        summary = answer_gen.generate(prompt, [{"text": context, "chunk_id": "summary"}])
        # Return a single NoteEntry matching the contracts.
        from app.contracts import NoteEntry

        return [
            NoteEntry(
                note_id="generated-note",
                lecture_id=str(config.get("lecture_id", "")),
                version=str(config.get("processing_version", "0")),
                section="Summary",
                title="Lecture Summary",
                description=summary,
                supporting_segment_ids=[
                    c.get("chunk_id") for c in authorized_timed_chunks if c.get("chunk_id")
                ],
            )
        ]

