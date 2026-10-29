import pytest
from pydantic import ValidationError

from app.config import Settings


def test_default_mode_is_mock_and_dev() -> None:
    settings = Settings(_env_file=None)
    assert settings.env == "dev"
    assert settings.processing_mode == "mock"


def test_mock_mode_is_rejected_in_production() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, env="production", processing_mode="mock")


def test_production_can_use_real_mode() -> None:
    settings = Settings(_env_file=None, env="production", processing_mode="real")
    assert settings.processing_mode == "real"
