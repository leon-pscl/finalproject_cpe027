"""Chunker implementation – splits a Transcript into overlapping time windows.

The chunker produces `Chunk` objects defined in `backend/app/contracts.py`.
It uses the `chunk_seconds` and `chunk_overlap_seconds` settings from `app.config`.
"""

from __future__ import annotations

import uuid
from typing import List
import logging
logger = logging.getLogger(__name__)

from app.contracts import Chunk
from app.asr import Transcript
from app.config import get_settings


class Chunker:
    """Create overlapping text chunks from a transcript.

    Each chunk covers a time interval of `chunk_seconds` with an overlap of
    `chunk_overlap_seconds` with the previous chunk. The resulting `Chunk`
    objects contain the concatenated text and a list of the underlying segment
    IDs that intersect the window.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.chunk_seconds = settings.chunk_seconds
        self.overlap_seconds = settings.chunk_overlap_seconds

    def chunk(self, transcript: Transcript, lecture_id: str, version: str) -> List[Chunk]:
        logger.info("Chunker: processing transcript with %d segments for lecture %s", len(transcript.segments), lecture_id)
        segments = transcript.segments
        if not segments:
            return []

        # Build timeline tuples (start, end, text, id)
        timeline = [(seg.start, seg.end, seg.text, seg.id) for seg in segments]
        total_end = max(end for _, end, _, _ in timeline)
        start = 0.0
        chunks: List[Chunk] = []
        while start < total_end:
            end = start + self.chunk_seconds
            # Determine which segments intersect this window
            seg_ids = [sid for s_start, s_end, _, sid in timeline if s_end > start and s_start < end]
            # Concatenate texts in order
            text_parts = [txt for s_start, s_end, txt, _ in timeline if s_end > start and s_start < end]
            text = " ".join(text_parts).strip()
            chunk = Chunk(
                chunk_id=f"chunk-{uuid.uuid4().hex[:8]}",
                lecture_id=lecture_id,
                version=version,
                segment_ids=seg_ids,
                start_s=round(start, 2),
                end_s=round(min(end, total_end), 2),
                text=text,
                embedding_model="",
                embedding_revision="",
            )
            chunks.append(chunk)
            # Advance start for next window, respecting overlap
            start = end - self.overlap_seconds
        return chunks
