"""Build audio arms for evaluation.

Each arm returns the path to a WAV file ready for ASR transcription.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure root and backend directories are in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import numpy as np
from scipy.io import wavfile

try:
    from app.media import extract_arm_a, process_local_audio, DSPConfig
    from app.dsp import enhance, write_wav
except ImportError:
    from backend.app.media import extract_arm_a, process_local_audio, DSPConfig
    from backend.app.dsp import enhance, write_wav


def load_audio(path: str) -> np.ndarray:
    sr, data = wavfile.read(path)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if data.dtype == np.int16:
        return data.astype(np.float32) / 32768.0
    if np.issubdtype(data.dtype, np.floating):
        return data.astype(np.float32)
    return data.astype(np.float32) / float(np.iinfo(data.dtype).max)


def build_arm_a(src_path: str, output_root: str = "eval/results/arms") -> Path:
    """Baseline Arm A: extract 16 kHz mono loudnorm (no DSP)."""
    out_root = Path(output_root)
    out_root.mkdir(parents=True, exist_ok=True)
    src = Path(src_path)
    arm_a_path = out_root / f"arm_a_{src.stem}.wav"
    extract_arm_a(src, arm_a_path)
    return arm_a_path


def build_arm_b(src_path: str, output_root: str = "eval/results/arms") -> Path:
    """Arm B: same as Arm A but with DSP stages enabled via DSPConfig."""
    out_root = Path(output_root)
    out_root.mkdir(parents=True, exist_ok=True)
    src = Path(src_path)
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
    """Arm C: Arm A audio passed through the classical Wiener+dereverb DSP enhancer."""
    out_root = Path(output_root)
    out_root.mkdir(parents=True, exist_ok=True)
    arm_a_path = build_arm_a(src_path, output_root)
    audio = load_audio(str(arm_a_path))
    enhanced, _ = enhance(audio)
    out_path = out_root / f"arm_c_{Path(src_path).stem}.wav"
    write_wav(str(out_path), enhanced)
    return out_path
