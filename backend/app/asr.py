"""Speech recognition with a pretrained Whisper model (faster-whisper). No training happens here."""

from __future__ import annotations

import math
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from . import dsp
from .config import get_settings

def _map_timestamp(t: float, offset_map: list[tuple[float, float, float]]) -> float:
    """Map a timestamp in the stripped audio back to the original timeline.
    ``offset_map`` is a list of ``(orig_start, orig_end, stripped_start)`` tuples.
    """
    for orig_start, orig_end, stripped_start in offset_map:
        seg_len = orig_end - orig_start
        if stripped_start <= t < stripped_start + seg_len:
            return orig_start + (t - stripped_start)
    # If not found, approximate by extending the last segment
    if offset_map:
        last_orig_start, last_orig_end, last_stripped_start = offset_map[-1]
        last_len = last_orig_end - last_orig_start
        if t >= last_stripped_start:
            return last_orig_end + (t - (last_stripped_start + last_len))
    return t
import time
import random
import numpy as np
import httpx

NO_SPEECH_DROP = 0.8  # drop segments the model is very sure are not speech


@dataclass
class Segment:
    id: str
    start: float
    end: float
    text: str
    confidence: float  # 0..1, derived from the model's mean token log-probability


@dataclass
class Transcript:
    language: str
    duration: float
    segments: list[Segment] = field(default_factory=list)
    offset_map: list[tuple[float, float, float]] | None = None  # (orig_start, orig_end, stripped_start)
    dsp: dict | None = None  # only asr.transcribe_file fills this; other providers leave it None


ProgressFn = Callable[[float], None]
SegmentFn = Callable[[Segment], None]
PhaseFn = Callable[[str], None]

_model = None
_model_lock = threading.Lock()


def get_model():
    """Load the model once (first call downloads it into MODEL_CACHE_DIR)."""
    global _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel

            s = get_settings()
            _model = WhisperModel(
                s.whisper_model,
                device=s.whisper_device,
                compute_type=s.whisper_compute_type,
                download_root=s.model_cache_dir,
            )
        return _model


def confidence_from_logprob(avg_logprob: float) -> float:
    return max(0.0, min(1.0, math.exp(avg_logprob)))


import logging

def transcribe_file(
    path: str,
    on_progress: ProgressFn | None = None,
    on_segment: SegmentFn | None = None,
    glossary: list[str] | None = None,
    model=None,
    enhance: bool | None = None,
    reverb_weight: float | None = None,
    on_phase: PhaseFn | None = None,
) -> Transcript:
    """Transcribe an audio/video file into timestamped segments.

    `model` is injectable so tests can run without downloading weights.
    """
    s = get_settings()
    logger = logging.getLogger(__name__)
    logger.info("ASR: starting transcription for %s (provider=%s)", path, s.asr_provider)
    if model is not None:
        # Use injected model later; continue with DSP handling below
        pass
    if s.asr_provider == "groq" and model is None:
        # Apply DSP if enhancement is enabled, then use Groq provider on the (possibly enhanced) audio file.
        # This mirrors the non‑Groq path: we run dsp.enhance, write the enhanced audio to a temporary wav,
        # and then call the provider with that file. Any DSP error is recorded in `dsp_info` and the
        # raw file is used as a fallback.
        from .groq_asr import transcribe_file as provider_transcribe
        import tempfile, os
        audio_path = path
        # Ensure audio is PCM‑16 WAV for Groq (fallback when no enhancement)
        if audio_path == path:
            fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            dsp.write_wav(tmp_path, dsp.load_audio(path))
            audio_path = tmp_path
        dsp_info: dict | None = None
        # Apply optional DSP enhancement, then strip silence and rewrite temp wav
        audio_np = dsp.load_audio(audio_path)
        if s.enhance_default if enhance is None else enhance:
            if on_phase:
                on_phase("enhancing")
            try:
                enhanced, report = dsp.enhance(
                    audio_np,
                    rt60=s.dsp_rt60,
                    floor_db=s.dsp_floor_db,
                    reverb_weight=s.dsp_reverb_weight if reverb_weight is None else reverb_weight,
                    noise_bias=s.dsp_noise_bias,
                    on_progress=(lambda p: on_progress(0.1 * p)) if on_progress else None,
                )
                audio_np = enhanced
                dsp_info = report.as_dict()
            except Exception as exc:  # noqa: BLE001
                dsp_info = {"applied": False, "error": f"{type(exc).__name__}: {exc}"}
        stripped_audio, offset_map = dsp.strip_silence(audio_np)
        fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        dsp.write_wav(tmp_path, stripped_audio)
        audio_path = tmp_path
        # (enhancement already applied above)
        # (Groq enhancement block removed)
        """

                    dsp.load_audio(path),
                    rt60=s.dsp_rt60,
                    floor_db=s.dsp_floor_db,
                    reverb_weight=s.dsp_reverb_weight if reverb_weight is None else reverb_weight,
                    noise_bias=s.dsp_noise_bias,
                    on_progress=(lambda p: on_progress(0.1 * p)) if on_progress else None,
                )
                # Write enhanced audio to a temporary wav file for Groq upload
                fd, tmp_path = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                dsp.write_wav(tmp_path, enhanced)
                audio_path = tmp_path
                dsp_info = report.as_dict()
            except Exception as exc:  # noqa: BLE001
                dsp_info = {"applied": False, "error": f"{type(exc).__name__}: {exc}"}
                # Ensure audio is PCM‑16 WAV for Groq (fallback when no enhancement)
                if audio_path == path:
                    fd, tmp_path = tempfile.mkstemp(suffix=".wav")
                    os.close(fd)
                    dsp.write_wav(tmp_path, dsp.load_audio(path))
                    audio_path = tmp_path


        """
        # Chunk and transcribe using Groq, respecting size limits and rate limits
        # Configuration: chunk size (seconds) and overlap (seconds) from Settings
        chunk_seconds = s.chunk_seconds
        overlap_seconds = s.chunk_overlap_seconds
        sr = dsp.SR
        chunk_samples = int(chunk_seconds * sr)
        overlap_samples = int(overlap_seconds * sr)

        total_requests = 0
        total_audio_seconds_sent = 0.0
        all_segments: list[Segment] = []

        # 429 retry/backoff lives in groq_http.post_with_retry; a second layer here would
        # multiply the attempts (5 x 5) and stall a single chunk for minutes.

        # Process audio in overlapping chunks
        start_idx = 0
        audio_len = len(stripped_audio)
        while start_idx < audio_len:
            end_idx = min(audio_len, start_idx + chunk_samples)
            chunk = stripped_audio[start_idx:end_idx]
            fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            dsp.write_wav(tmp_path, chunk)

            chunk_transcript = provider_transcribe(
                tmp_path,
                on_progress=on_progress,
                on_segment=on_segment,
                glossary=glossary,
                model=model,
                enhance=False,
                reverb_weight=None,
                on_phase=on_phase,
            )

            # Adjust timestamps: each segment start/end is relative to the chunk's position in the stripped audio.
            chunk_start_stripped = start_idx / sr
            for seg in chunk_transcript.segments:
                orig_start = _map_timestamp(seg.start + chunk_start_stripped, offset_map)
                orig_end = _map_timestamp(seg.end + chunk_start_stripped, offset_map)
                seg.start = round(orig_start, 2)
                seg.end = round(orig_end, 2)
                all_segments.append(seg)

            total_requests += 1
            total_audio_seconds_sent += len(chunk) / sr
            os.remove(tmp_path)

            # Advance start with overlap
            start_idx = end_idx - overlap_samples if end_idx < audio_len else end_idx

        # Build final transcript
        transcript = Transcript(
            language=chunk_transcript.language,
            duration=len(stripped_audio) / sr,
            segments=all_segments,
            dsp=dsp_info,
            offset_map=offset_map,
        )
        logger.info(
            "Groq ASR: %d requests, %.2f audio‑seconds sent",
            total_requests,
            total_audio_seconds_sent,
        )
        # Clean up temporary stripped‑audio file
        if audio_path != path:
            try:
                os.remove(audio_path)
            except OSError:
                pass
        return transcript
    audio = path
    dsp_info: dict | None = None
    base = 0.0
    if s.enhance_default if enhance is None else enhance:
        if on_phase:
            on_phase("enhancing")
        try:
            enhanced, report = dsp.enhance(
                dsp.load_audio(path),
                rt60=s.dsp_rt60,
                floor_db=s.dsp_floor_db,
                reverb_weight=s.dsp_reverb_weight
                if reverb_weight is None
                else reverb_weight,
                noise_bias=s.dsp_noise_bias,
                on_progress=(lambda p: on_progress(0.1 * p)) if on_progress else None,
            )
            audio, dsp_info, base = enhanced, report.as_dict(), 0.1
        except Exception as exc:  # noqa: BLE001 - recorded in the result; transcription continues on the raw audio
            dsp_info = {"applied": False, "error": f"{type(exc).__name__}: {exc}"}
    if on_phase:
        on_phase("transcribing")
    model = model or get_model()
    logger.info("ASR model loaded: %s", getattr(model, "model_name", "unknown"))
    stream, info = model.transcribe(
        audio,
        language=None
        if s.whisper_language.lower() in ("", "auto")
        else s.whisper_language,
        beam_size=5,
        vad_filter=True,  # skip silence/noise; also reduces hallucinated text
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,  # avoids repetition loops on long lectures
        initial_prompt=", ".join(glossary) if glossary else None,
    )
    duration = float(info.duration or 0.0)
    result = Transcript(language=info.language, duration=duration)
    for raw in stream:
        text = raw.text.strip()
        if not text or (raw.no_speech_prob or 0.0) > NO_SPEECH_DROP:
            continue
        seg = Segment(
            id=f"seg-{len(result.segments) + 1}",
            start=round(float(raw.start), 2),
            end=round(float(raw.end), 2),
            text=text,
            confidence=round(confidence_from_logprob(raw.avg_logprob), 3),
        )
        result.segments.append(seg)
        if on_segment:
            on_segment(seg)
        if on_progress and duration > 0:
            on_progress(base + (1 - base) * min(0.99, float(raw.end) / duration))
    result.dsp = dsp_info
    logger.info("ASR transcription completed – %d segments", len(result.segments))
    return result
