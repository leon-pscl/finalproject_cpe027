"""Build audio arms for evaluation.

Each arm returns the path to a WAV file ready for ASR transcription.
"""

import os
from pathlib import Path
from typing import Tuple

from backend.app.media import extract_arm_a, process_local_audio, DSPConfig
from backend.app.dsp import enhance


def build_arm_a(src_path: str, output_root: str = "eval/results/arms") -> Path:
    """Baseline Arm A: extract 16 kHz mono loudnorm (no DSP)."""
    out_root = Path(output_root)
    out_root.mkdir(parents=True, exist_ok=True)
    src = Path(src_path)
    arm_a_path = out_root / f"arm_a_{src.stem}.wav"
    # Use the same extraction as media pipeline
    extract_arm_a(src, arm_a_path)
    return arm_a_path


def build_arm_b(src_path: str, output_root: str = "eval/results/arms") -> Path:
    """Arm B: same as Arm A but with DSP stages enabled via Settings.

    We reuse `process_local_audio` with a config that has `bypass=False`.
    """
    out_root = Path(output_root)
    out_root.mkdir(parents=True, exist_ok=True)
    src = Path(src_path)
    # Build a DSPConfig that mirrors the current Settings but forces DSP on
    cfg = DSPConfig(
        version="eval-arm-b",
        bypass=False,
        high_pass_enabled=True,
        high_pass_cutoff_hz=80.0,
        spectral_gating_enabled=False,
        normalize=True,
        vad_enabled=False,
        target_sample_rate=16_000,
        target_channels=1,
    )
    result = process_local_audio(src, cfg, output_root=out_root)
    return Path(result.dsp_path)


def build_arm_c(src_path: str, output_root: str = "eval/results/arms") -> Path:
    """Arm C: Arm A audio passed through the classical DSP enhancer.
    """
    out_root = Path(output_root)
    out_root.mkdir(parents=True, exist_ok=True)
    # First get Arm A baseline
    arm_a_path = build_arm_a(src_path, output_root)
    # Load audio array
    audio = enhance.load_audio(str(arm_a_path))
    # Run enhancer (default params)
    enhanced, _ = enhance(audio)
    out_path = out_root / f"arm_c_{Path(src_path).stem}.wav"
    from backend.app.dsp import write_wav

    write_wav(str(out_path), enhanced)
    return out_path
