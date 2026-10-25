<<<<<<< HEAD
<<<<<<< HEAD
"""Application configuration.

Values are read from environment variables (and a local `.env` file in
development). No secrets are read from committed files.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Env = Literal["dev", "staging", "production"]
ProcessingMode = Literal["mock", "real"]


class Settings(BaseSettings):
    """Runtime settings; validated on load."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Runtime posture
    env: Env = "dev"
    processing_mode: ProcessingMode = "mock"
    asr_provider: str = "none"
    embed_provider: str = "none"
    llm_provider: str = "none"
    dsp_enabled: bool = False

    # Upload and processing limits (verified per deployment; defaults are safe)
    max_upload_mb: int = Field(default=512, gt=0, le=4096)
    max_duration_minutes: int = Field(default=60, gt=0, le=240)
    per_user_daily_job_limit: int = Field(default=5, gt=0)
    per_user_lecture_limit: int = Field(default=25, gt=0)

    # Firebase
    firebase_project_id: str | None = None
    firebase_storage_bucket: str | None = None
    firebase_credentials_path: str | None = None
    firebase_auth_emulator_host: str | None = None
    firestore_emulator_host: str | None = None
    firebase_storage_emulator_host: str | None = None

    # Provider configuration (keys stay server-side; never committed)
    openai_api_key: str | None = None
    custom_asr_base_url: str | None = None

    repository_backend: Literal["auto", "firestore", "memory"] = "auto"
    local_storage_root: str = "local_storage"
    storage_signed_url_secret: str = "local-dev-storage-secret"

    # DSP
    dsp_version: str = "0"
    dsp_high_pass_cutoff_hz: float = Field(default=80.0, ge=1.0, le=500.0)
    dsp_spectral_gating_enabled: bool = False

    @model_validator(mode="after")
    def _reject_mock_in_production(self) -> Settings:
        if self.env == "production" and self.processing_mode == "mock":
            raise ValueError("PROCESSING_MODE=mock is not allowed when ENV=production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    """Test helper to reload settings from environment."""
    get_settings.cache_clear()
=======
=======
>>>>>>> iteration_lim
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
<<<<<<< HEAD
>>>>>>> iteration_lim
=======
>>>>>>> iteration_lim
