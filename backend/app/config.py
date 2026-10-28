"""Application configuration.

Values are read from environment variables (and a local `.env` file in
development). No secrets are read from committed files.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, model_validator
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
        populate_by_name=True,
    )

    # Runtime posture
    env: Env = "dev"
    processing_mode: ProcessingMode = "mock"
    asr_provider: Literal["none", "faster-whisper", "groq"] = "none"
    embed_provider: Literal["none", "mock", "openai"] = "none"
    llm_provider: str = "none"
    dsp_enabled: bool = False

    chunk_seconds: int = Field(default=30, gt=1, description="Chunk length in seconds")
    chunk_overlap_seconds: int = Field(default=5, ge=0, description="Overlap between chunks")

    max_duration_minutes: int = Field(default=60, gt=0, le=240)
    per_user_daily_job_limit: int = Field(default=5, gt=0)
    max_upload_mb: int = Field(default=512, gt=0, description="Maximum upload size in megabytes")
    per_user_lecture_limit: int = Field(default=25, gt=0)
    workers: int = Field(
        default=1, gt=0, validation_alias=AliasChoices("TRANSCRIBE_WORKERS", "workers")
    )
    job_ttl_seconds: int = Field(default=24 * 3600, gt=0)
    worker_enabled: bool = True

    # Firebase
    firebase_project_id: str | None = None
    firebase_storage_bucket: str | None = None
    firebase_credentials_path: str | None = None
    firebase_auth_emulator_host: str | None = None
    firestore_emulator_host: str | None = None
    firebase_storage_emulator_host: str | None = None

    # Provider configuration (keys stay server-side; never committed)
    openai_api_key: str | None = None
    groq_api_key: str | None = None
    custom_asr_base_url: str | None = None

    repository_backend: Literal["auto", "firestore", "memory"] = "auto"
    local_storage_root: str = "local_storage"
    storage_signed_url_secret: str = "local-dev-storage-secret"

    # Pretrained Whisper model run through faster-whisper (CTranslate2).
    # tiny | base | small | medium | large-v3 | distil-large-v3 ...
    whisper_model: str = "small"
    whisper_device: str = "auto"  # auto | cpu | cuda
    whisper_compute_type: str = "int8"  # int8 for CPU; float16 for GPU
    # "" (empty) = auto-detect, needed for Filipino/English code-switching; or force "en" / "tl".
    whisper_language: str = ""
    model_cache_dir: str = "/models"

    # DSP
    dsp_version: str = "0"
    dsp_high_pass_cutoff_hz: float = Field(default=80.0, ge=1.0, le=500.0)
    dsp_spectral_gating_enabled: bool = False
    # dsp.py enhancement for POST /api/transcriptions. Off by default so the upload
    # pipeline runs media.py DSP exactly once; app.evaluate passes enhance= itself.
    enhance_default: bool = Field(
        default=False, validation_alias=AliasChoices("ENHANCE_AUDIO", "enhance_default")
    )
    dsp_rt60: float = 0.5
    dsp_floor_db: float = -15.0
    dsp_reverb_weight: float = 0.0  # 0 = denoise only
    dsp_noise_bias: float = 1.5

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
