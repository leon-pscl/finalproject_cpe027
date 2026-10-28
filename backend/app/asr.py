"""Speech recognition with a pretrained Whisper model (faster-whisper). No training happens here."""

from __future__ import annotations

import math
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from . import dsp
from .config import get_settings

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
    dsp: dict | None = None  # enhancement report (None when enhancement was off)


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
    if model is not None:
        # Use injected model later; continue with DSP handling below
        pass
    if s.asr_provider == "groq" and model is None:
        from .groq_asr import transcribe_file as provider_transcribe
        return provider_transcribe(
            path,
            on_progress=on_progress,
            on_segment=on_segment,
            glossary=glossary,
            model=model,
            enhance=enhance,
            reverb_weight=reverb_weight,
            on_phase=on_phase,
        )
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
    result = Transcript(language=info.language, duration=duration, dsp=dsp_info)
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
    return result
