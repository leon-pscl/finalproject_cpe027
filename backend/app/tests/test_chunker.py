"""Tests for the Chunker implementation.

We construct a simple Transcript with three segments and verify the overlapping
chunks produced by the Chunker class.
"""

from __future__ import annotations

import uuid

from app.chunker import Chunker
from app.asr import Transcript, Segment


def make_transcript() -> Transcript:
    segs = [
        Segment(id="s1", start=0.0, end=5.0, text="Hello world", confidence=0.9),
        Segment(id="s2", start=5.0, end=10.0, text="Testing chunk", confidence=0.9),
        Segment(id="s3", start=10.0, end=15.0, text="Final part", confidence=0.9),
    ]
    return Transcript(language="en", duration=15.0, segments=segs)


def test_chunker_overlap():
    transcript = make_transcript()
    # Use a small chunk size to force overlap
    chunker = Chunker()
    # Monkey‑patch settings via the get_settings import inside Chunker – we rely on defaults (30s/5s)
    # For this test we manually set the attributes after construction.
    chunker.chunk_seconds = 6
    chunker.overlap_seconds = 2
    chunks = chunker.chunk(transcript, lecture_id="demo", version="v1")
    assert len(chunks) == 4
    # Expected windows: [0‑6], [4‑10], [8‑14], [12‑15]
    starts = [c.start_s for c in chunks]
    ends = [c.end_s for c in chunks]
    assert starts == [0.0, 4.0, 8.0, 12.0]
    assert ends == [6.0, 10.0, 14.0, 15.0]
    # Verify that segment IDs are correctly associated
    assert chunks[0].segment_ids == ["s1", "s2"]
    assert chunks[1].segment_ids == ["s1", "s2"]
    assert chunks[2].segment_ids == ["s2", "s3"]
    assert chunks[3].segment_ids == ["s3"]
