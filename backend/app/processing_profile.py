"""Validated processing profiles shared by JobStore, the lecture worker, and evaluation metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ConfigDict, Field

from .contracts import ProcessingOptions
from .media import DSPConfig

BASELINE_PROFILE_VERSION = "1"
BASELINE_LEVEL_TARGET_DB = -20.0


@dataclass(frozen=True)
class ResolvedProcessingProfile:
    """One effective media configuration and its provenance."""

    schema_version: str
    options: ProcessingOptions
    config: DSPConfig
    applied_enhancement: bool
    requested_profile: str
    level_policy_id: str
    operations_applied: dict[str, bool]


def _baseline_options() -> ProcessingOptions:
    return ProcessingOptions(schema_version=BASELINE_PROFILE_VERSION)


def _effective_stage_flags(
    settings: Any, options: ProcessingOptions
) -> tuple[bool, bool, int, str | None]:
    """Resolve FFmpeg media staging controls with explicit policy validation."""
    high_pass = bool(options.high_pass_enabled)
    denoising = bool(options.background_noise_reduction_enabled)
    cutoff = int(options.high_pass_cutoff_hz)
    cutoffs = getattr(settings, "dsp_allowed_high_pass_cutoffs", None)
    if cutoffs is not None and cutoff not in cutoffs:
        raise ValueError(f"unsupported high-pass cutoff: {cutoff}")

    experimental_allowed = bool(getattr(settings, "dsp_experimental_controls_enabled", False))
    requested_profile = options.requested_profile or ("baseline" if options.high_pass_enabled is False and options.background_noise_reduction_enabled is False else "experimental")
    if requested_profile != "baseline" or options.experimental_enhancement_enabled or options.dsp_enabled:
        if not experimental_allowed:
            raise ValueError("experimental DSP controls are not enabled by server policy")
    # Keep the legacy master switch from implying any individual stage. Do not
    # reject an explicit stage solely because this backward-compatible flag is off.
    return high_pass, denoising, cutoff, None


def resolve_processing_options(settings: Any, options: ProcessingOptions | None) -> ResolvedProcessingProfile:
    """Resolve and validate options into one media configuration."""
    raw = options if options is not None else _baseline_options()
    parsed = ProcessingOptions.model_validate(raw.model_dump() if hasattr(raw, "model_dump") else raw)
    arm = parsed.dsp_arm
    if arm:
        high_pass = arm != "arm_a"
        denoising = False
        cutoff = int(parsed.high_pass_cutoff_hz)
        warning = None
    else:
        high_pass, denoising, cutoff, warning = _effective_stage_flags(settings, parsed)

    # Both the server switch and explicit stage toggles can activate the media
    # preparation DSP path. Individual stage flags remain independent; a master
    # switch does not silently imply high-pass or spectral gating.
    master = bool(getattr(settings, "dsp_enabled", False))
    optional_stage = bool(high_pass or denoising or bool(parsed.dsp_enabled))
    bypass = not (master or optional_stage)

    config = DSPConfig(
        bypass=bypass,
        evaluation_arm=arm or "",
        high_pass_enabled=high_pass,
        high_pass_cutoff_hz=float(cutoff),
        spectral_gating_enabled=denoising,
        spectral_gating_strength_db=25.0,
        normalize=True,
        target_sample_rate=16000,
        target_channels=1,
    )

    return ResolvedProcessingProfile(
        schema_version=parsed.schema_version or BASELINE_PROFILE_VERSION,
        options=parsed,
        config=config,
        applied_enhancement=False,
        requested_profile=parsed.requested_profile or (f"dsp_arm:{arm}" if arm else ("baseline" if not (high_pass or denoising) else "experimental")),
        level_policy_id="loudnorm-i20-tp-2-lra7",
        operations_applied={
            "decode_validate": True,
            "mono_16k": True,
            "high_pass": config.high_pass_enabled and not config.bypass,
            "spectral_gating": config.spectral_gating_enabled and not config.bypass,
            "normalize": config.normalize,
            "asr_side_enhancement": False,
        },
    )


def resolve_from_mapping(settings: Any, mapping: dict | None) -> ResolvedProcessingProfile:
    if mapping is None:
        return resolve_processing_options(settings, None)
    return resolve_processing_options(settings, ProcessingOptions.model_validate(mapping))


# Tell Pydantic 2 that config fields here do not pretend to be models.
__all__ = ["ResolvedProcessingProfile", "resolve_processing_options", "resolve_from_mapping"]