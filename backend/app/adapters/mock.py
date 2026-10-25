"""Mock adapters for safe local development and tests.

Every value produced here is labeled as mock/demo output. Mock mode is rejected in
production by application configuration.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.contracts import (
    AnswerBlock,
    AnswerResponse,
    AnswerStatus,
    Chunk,
    NoteEntry,
    SourceReference,
    TranscriptSegment,
)


class MockMediaService:
    def validate_and_extract(
        self, lecture_id: str, processing_version: str
    ) -> dict[str, Any]:
        return {
            "lecture_id": lecture_id,
            "processing_version": processing_version,
            "audio_asset": {"type": "mock", "duration_s": 120.0},
            "media_metadata": {"content_type": "audio/wav", "size_bytes": 1024},
            "demo": True,
        }


class MockAudioProcessor:
    def process(self, audio_asset: Any, config: dict[str, Any]) -> Any:
        return {
            "audio_asset": audio_asset,
            "normalized": True,
            "dsp_config": config,
            "demo": True,
        }


class MockTranscriber:
    def transcribe(
        self, audio_asset: Any, config: dict[str, Any]
    ) -> list[TranscriptSegment]:
        return [
            TranscriptSegment(
                segment_id="demo-seg-1",
                lecture_id=str(config.get("lecture_id", "demo")),
                version=str(config.get("processing_version", "0")),
                order=0,
                start_s=0.0,
                end_s=5.0,
                text="Demo output - not processed from this upload.",
                diagnostic_flags=["mock"],
            )
        ]


class MockChunker:
    def chunk(
        self, timed_segments: Sequence[TranscriptSegment], config: dict[str, Any]
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        for segment in timed_segments:
            chunks.append(
                Chunk(
                    chunk_id=f"mock-chunk-{segment.segment_id}",
                    lecture_id=segment.lecture_id,
                    version=segment.version,
                    segment_ids=[segment.segment_id],
                    start_s=segment.start_s,
                    end_s=segment.end_s,
                    text=segment.text,
                    embedding_model="mock",
                    embedding_revision="0",
                )
            )
        return chunks


class MockEmbedder:
    def embed(self, texts: Sequence[str], config: dict[str, Any]) -> list[list[float]]:
        return [[0.0, 0.0, 0.0] for _ in texts]


class MockRetriever:
    def search(
        self, owner_id: str, lecture_id: str, processing_version: str, question: str
    ) -> list[Chunk]:
        return []


class MockAnswerGenerator:
    def answer(
        self,
        question: str,
        authorized_evidence: Sequence[Chunk],
        config: dict[str, Any],
    ) -> AnswerResponse:
        sources = [
            SourceReference(
                source_id=chunk.chunk_id,
                segment_id=chunk.segment_ids[0] if chunk.segment_ids else None,
                start_s=chunk.start_s,
                end_s=chunk.end_s,
                text=chunk.text,
            )
            for chunk in authorized_evidence
        ]
        if not authorized_evidence:
            return AnswerResponse(
                answer_id="mock-answer",
                lecture_id=str(config.get("lecture_id", "")),
                version=str(config.get("processing_version", "0")),
                processing_mode="mock",
                status=AnswerStatus.INSUFFICIENT_EVIDENCE,
                blocks=[],
                sources=[],
            )
        return AnswerResponse(
            answer_id="mock-answer",
            lecture_id=str(config.get("lecture_id", "")),
            version=str(config.get("processing_version", "0")),
            processing_mode="mock",
            status=AnswerStatus.ANSWERED,
            blocks=[
                AnswerBlock(
                    block_id="b1",
                    text="Demo answer from mock evidence.",
                    source_ids=[authorized_evidence[0].chunk_id],
                )
            ],
            sources=sources,
        )


class MockNotesGenerator:
    def generate(
        self, authorized_timed_chunks: Sequence[Chunk], config: dict[str, Any]
    ) -> list[NoteEntry]:
        return [
            NoteEntry(
                note_id="mock-note",
                lecture_id=str(config.get("lecture_id", "")),
                version=str(config.get("processing_version", "0")),
                section="Demo",
                title="Mock note",
                description="Demo output - not processed from this upload.",
                supporting_segment_ids=[
                    chunk.segment_ids[0]
                    for chunk in authorized_timed_chunks
                    if chunk.segment_ids
                ],
            )
        ]


# Protocol satisfaction is structural; these aliases document intent.
_: Any = [
    MockMediaService,
    MockAudioProcessor,
    MockTranscriber,
    MockChunker,
    MockEmbedder,
    MockRetriever,
    MockAnswerGenerator,
    MockNotesGenerator,
]
