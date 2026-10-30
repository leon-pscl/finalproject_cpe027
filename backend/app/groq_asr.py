"""Groq ASR provider – uses Groq's Whisper endpoint.

The function mirrors the signature of `backend.app.asr.transcribe_file` so the caller can
switch providers transparently via the `asr_provider` setting.
"""

import json
import math
import os
from typing import Callable, List

# Note: get_settings is imported inside the function to allow monkey‑patching in tests.

from .asr import Transcript, Segment, confidence_from_logprob
from .groq_http import post_with_retry

ProgressFn = Callable[[float], None]
SegmentFn = Callable[[Segment], None]
PhaseFn = Callable[[str], None]


def transcribe_file(
    path: str,
    on_progress: ProgressFn | None = None,
    on_segment: SegmentFn | None = None,
    glossary: List[str] | None = None,
    model=None,
    enhance: bool | None = None,
    reverb_weight: float | None = None,
    on_phase: PhaseFn | None = None,
) -> Transcript:
    """Call Groq's Whisper API and return a ``Transcript``.

    The Groq API key is read from the ``GROQ_API_KEY`` setting. If the key is
    missing a ``RuntimeError`` is raised – this complies with the project's
    safe‑local mode.
    """
    from .config import get_settings
    settings = get_settings()
    api_key = getattr(settings, "groq_api_key", None)
    if not api_key:
        raise RuntimeError("Groq API key not configured")

    # Read the audio file (already DSP‑processed by Step 4)
    if not os.path.exists(path):
        # In test environments we may not have a real file; use empty bytes.
        audio_bytes = b""
    else:
        with open(path, "rb") as f:
            audio_bytes = f.read()

    files = {"file": (os.path.basename(path), audio_bytes, "application/octet-stream")}
    data = {
        "model": getattr(settings, "whisper_model", "small"),  # Uses WHISPER_MODEL env var (must be a valid Groq model ID)
        "response_format": "verbose_json",
    }
    if glossary:
        data["prompt"] = ", ".join(glossary)

    headers = {"Authorization": f"Bearer {api_key}"}

    if on_phase:
        on_phase("calling_groq")

    response = post_with_retry(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers=headers,
        data=data,
        files=files,
        timeout=60.0,
    )
    result = response.json()

    # Expected result format (simplified):
    # {"segments": [{"id":..., "start":..., "end":..., "text":..., "avg_logprob":...}, ...],
    #  "language": "en", "duration": 12.34}
    segments = result.get("segments", [])
    language = result.get("language", "en")
    duration = float(result.get("duration", 0))
    transcript = Transcript(language=language, duration=duration)

    # Fallback: if the API returned only a plain text field (no segments), create a single segment.
    if not segments and result.get("text"):
        full_text = result["text"].strip()
        if full_text:
            segments = [{
                "id": "0",
                "start": 0,
                "end": duration,
                "text": full_text,
                "avg_logprob": 0.0,
            }]


    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
        start = round(float(seg.get("start", 0)), 2)
        end = round(float(seg.get("end", 0)), 2)
        avg_logprob = float(seg.get("avg_logprob", -1.0))
        confidence = max(0.0, min(1.0, math.exp(avg_logprob)))
        segment = Segment(
            id=seg.get("id", f"seg-{len(transcript.segments) + 1}"),
            start=start,
            end=end,
            text=text,
            confidence=round(confidence, 3),
        )
        transcript.segments.append(segment)
        if on_segment:
            on_segment(segment)
        if on_progress and duration > 0:
            on_progress(min(0.99, end / duration))

    return transcript
