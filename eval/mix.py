"""Mix clean speech with noise for Tier 1 evaluation.

The mixer creates deterministic mixes at a given SNR using a seeded random
onset. All output files are written under `eval/results/mixes/` which is git‑ignored.
"""

import json
import random
from pathlib import Path
from typing import Dict

from backend.app.dsp import load_audio, normalize_loudness


def rms(samples) -> float:
    """Root‑mean‑square of a float array."""
    import math

    return math.sqrt(sum(s * s for s in samples) / len(samples))


def mix_clean_noise(
    clean_path: str,
    noise_path: str,
    snr_db: float,
    seed: int,
    out_dir: str = "eval/results/mixes",
) -> Dict:
    """Return a manifest dict for the created mix.

    * `clean_path` – path to the clean speech WAV (already 16 kHz mono).
    * `noise_path` – path to a noise WAV (any length, will be trimmed/padded).
    * `snr_db` – desired signal‑to‑noise ratio in decibels.
    * `seed` – deterministic seed for random onset selection.
    """
    random.seed(seed)
    out_dir_path = Path(out_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)

    # Load audio (returns np.ndarray of float32)
    clean = load_audio(clean_path)
    noise = load_audio(noise_path)

    # Ensure noise at least as long as clean – repeat if needed
    if len(noise) < len(clean):
        repeats = (len(clean) // len(noise)) + 1
        noise = (noise * repeats)[: len(clean)]
    else:
        # Random onset within noise
        max_start = len(noise) - len(clean)
        start = random.randint(0, max_start)
        noise = noise[start : start + len(clean)]

    # Scale noise to achieve target SNR
    clean_rms = rms(clean)
    noise_rms = rms(noise)
    # Desired noise RMS = clean_rms / (10^(snr/20))
    target_noise_rms = clean_rms / (10 ** (snr_db / 20))
    if noise_rms > 0:
        scale = target_noise_rms / noise_rms
    else:
        scale = 0.0
    noise = noise * scale

    mixed = clean + noise
    # Apply clipping protection and loudness normalisation (same as media pipeline)
    mixed = normalize_loudness(mixed)

    out_path = out_dir_path / f"mix_{Path(clean_path).stem}_snr{snr_db}_seed{seed}.wav"
    # Write WAV using dsp.write_wav
    from backend.app.dsp import write_wav

    write_wav(str(out_path), mixed)

    manifest = {
        "seed": seed,
        "clean_path": clean_path,
        "noise_path": noise_path,
        "snr_db": snr_db,
        "output_path": str(out_path),
    }
    # Save a small JSON side‑car for reproducibility
    json_path = out_path.with_suffix('.json')
    json_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest
