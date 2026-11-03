from types import SimpleNamespace

import pytest

from app.processing_profile import resolve_processing_options
from app.contracts import ProcessingOptions


def _settings(**kwargs):
    base = SimpleNamespace(
        dsp_experimental_controls_enabled=False,
        dsp_allowed_high_pass_cutoffs=[40, 80, 160],
    )
    base.__dict__.update(kwargs)
    return base


def test_default_profile_is_conservative_baseline():
    profile = resolve_processing_options(_settings(), None)
    assert profile.options.high_pass_enabled is False
    assert profile.options.background_noise_reduction_enabled is False
    assert profile.config.bypass is True
    assert profile.config.high_pass_enabled is False
    assert profile.config.spectral_gating_enabled is False
    assert profile.config.normalize is True
    assert profile.applied_enhancement is False
    assert profile.operations_applied == {
        "decode_validate": True,
        "mono_16k": True,
        "high_pass": False,
        "spectral_gating": False,
        "normalize": True,
        "asr_side_enhancement": False,
    }


def test_high_pass_is_independent():
    profile = resolve_processing_options(
        _settings(dsp_experimental_controls_enabled=True), ProcessingOptions(high_pass_enabled=True, high_pass_cutoff_hz=160)
    )
    assert profile.config.bypass is False
    assert profile.config.high_pass_enabled is True
    assert profile.config.spectral_gating_enabled is False
    assert profile.config.high_pass_cutoff_hz == 160


def test_background_denoising_is_independent():
    profile = resolve_processing_options(
        _settings(dsp_experimental_controls_enabled=True), ProcessingOptions(background_noise_reduction_enabled=True)
    )
    assert profile.config.bypass is False
    assert profile.config.high_pass_enabled is False
    assert profile.config.spectral_gating_enabled is True


def test_both_stages_can_be_enabled():
    profile = resolve_processing_options(
        _settings(dsp_experimental_controls_enabled=True),
        ProcessingOptions(high_pass_enabled=True, background_noise_reduction_enabled=True),
    )
    assert profile.config.high_pass_enabled is True
    assert profile.config.spectral_gating_enabled is True


def test_unsupported_cutoff_rejected():
    with pytest.raises(ValueError):
        resolve_processing_options(
            _settings(dsp_allowed_high_pass_cutoffs=[80]),
            ProcessingOptions(high_pass_enabled=True, high_pass_cutoff_hz=160),
        )


def test_experimental_access_rejected_without_server_policy():
    with pytest.raises(ValueError):
        resolve_processing_options(
            _settings(dsp_experimental_controls_enabled=False),
            ProcessingOptions(requested_profile="experimental"),
        )