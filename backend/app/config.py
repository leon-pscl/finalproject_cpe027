"""Runtime settings, read from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # Pretrained Whisper model run through faster-whisper (CTranslate2).
    # tiny | base | small | medium | large-v3 | distil-large-v3 ...
    whisper_model: str = os.environ.get("WHISPER_MODEL", "small")
    whisper_device: str = os.environ.get("WHISPER_DEVICE", "auto")  # auto | cpu | cuda
    whisper_compute_type: str = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")  # int8 for CPU; float16 for GPU
    # "auto" (or empty) = auto-detect (needed for Filipino/English code-switching); or force "en" / "tl".
    whisper_language: str = os.environ.get("WHISPER_LANGUAGE", "")
    model_cache_dir: str = os.environ.get("MODEL_CACHE_DIR", "/models")
    # DSP enhancement (runs before ASR). Defaults are conservative; verify with `python -m app.evaluate`.
    enhance_default: bool = os.environ.get("ENHANCE_AUDIO", "true").lower() in ("1", "true", "yes", "on")
    dsp_rt60: float = float(os.environ.get("DSP_RT60", "0.5"))
    dsp_floor_db: float = float(os.environ.get("DSP_FLOOR_DB", "-15"))
    dsp_reverb_weight: float = float(os.environ.get("DSP_REVERB_WEIGHT", "0.0"))  # 0 = denoise only
    dsp_noise_bias: float = float(os.environ.get("DSP_NOISE_BIAS", "1.5"))
    max_upload_mb: int = _int("MAX_UPLOAD_MB", 300)
    job_ttl_seconds: int = _int("JOB_TTL_SECONDS", 24 * 3600)
    workers: int = _int("TRANSCRIBE_WORKERS", 1)


def get_settings() -> Settings:
    return Settings()
