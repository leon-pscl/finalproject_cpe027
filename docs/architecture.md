# Evaluation Pipeline Architecture

## Preprocessing Contract

All ablation arms share a single decode step:

1. Decode/resample the source audio to mono 16 kHz.
2. Optionally apply one DSP stage (high-pass, Wiener, or FFmpeg denoise).
3. Apply exactly one final loudness normalisation (`loudnorm=I=-20:TP=-2:LRA=7`).

No arm may normalise twice, and no arm may apply enhancement after the final level.

## Arms

| Arm | Pipeline |
|-----|----------|
| A (`arm_a`) | prepared → loudnorm |
| B (`hp`) | prepared → high-pass → loudnorm |
| C (`hp_wiener`) | B prenorm → Wiener (dereverb=0) → loudnorm |
| D (`hp_wiener_oa`) | blend(B prenorm, C prenorm, OA weight) → loudnorm |
| E (`hp_ffmpeg`) | B prenorm → FFmpeg `afftdn` → loudnorm |

## Bootstrap CI

Optional `--bootstrap-ci` flag resamples per-talk means and reports a 95 % percentile interval.
