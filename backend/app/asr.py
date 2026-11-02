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
import shutil
import os
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
            import os

            os.environ.setdefault("OMP_NUM_THREADS", "1")
            os.environ.setdefault("MKL_NUM_THREADS", "1")
            os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

            from faster_whisper import WhisperModel

            s = get_settings()
            _model = WhisperModel(
                s.whisper_model,
                device=s.whisper_device,
                compute_type=s.whisper_compute_type,
                download_root=s.model_cache_dir,
                cpu_threads=1,
                num_workers=1,
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
    dsp_audio_out: str | None = None,
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
        logger.info("ASR phase: transcribing")
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
        logger.debug("ASR segment %s [%.2f-%.2f]: %s", seg.id, seg.start, seg.end, seg.text)
        if on_segment:
            on_segment(seg)
        if on_progress and duration > 0:
            on_progress(base + (1 - base) * min(0.99, float(raw.end) / duration))
    if dsp_audio_out is not None:
        from pathlib import Path
        output = Path(dsp_audio_out)
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            if isinstance(audio, np.ndarray):
                dsp.write_wav(str(output), audio)
            else:
                source = Path(audio)
                if source != Path(path):
                    try:
                        shutil.copyfile(source, output)
                    except Exception:
                        dsp.write_wav(str(output), dsp.load_audio(str(source)))
                else:
                    dsp.write_wav(str(output), dsp.load_audio(path))
            info = dsp_info if isinstance(dsp_info, dict) else {}
            info["audio_path"] = str(output)
            dsp_info = info
        except Exception as exc:  # noqa: BLE001
            info = dsp_info if isinstance(dsp_info, dict) else {}
            info["error"] = str(exc)
            dsp_info = info
    result.dsp = dsp_info
    logger.info("ASR transcription completed – %d segments", len(result.segments))
    return result
