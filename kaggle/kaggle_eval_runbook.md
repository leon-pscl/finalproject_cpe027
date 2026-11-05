# Kaggle Evaluation Run — procedure (short version)

Run the ASR/DSP eval on Kaggle using already-preprocessed local data. No preprocessing is redone.

## Setup (Kaggle notebook: `kaggle/kaggle_eval.ipynb`)

1. Mount datasets: `acl6060`, `demand`, and the M3AV split dataset(s) (auto-discovered by the notebook under `/kaggle/input/*/M3AV/extracted`).
2. First cells: `nvidia-smi`, `df -h`, `ls /kaggle/input/*`, eval deps install, versions, mount verification.
3. Env: Whisper `base` + `cuda` + `float16`, threads 4, language `en`; outputs to `/kaggle/working/...`.

## Smoke

```
python -m app.eval_runner --tier all --limit 1 --conditions arm_a,hp --snrs 0 --noise demand \
  --demand-envs DKITCHEN,DLIVING,DWASHING --data-root /kaggle/input/acl6060 \
  --demand-root /kaggle/input/demand --m3av-root $M3AV_CLIP_ROOT --out /kaggle/working/eval_smoke
```

Check printed WER/RTF before full runs.

## Full runs (fresh, `--no-resume`)

```bash
# Tier 1 — ACL6060 + seeded DEMAND noise (eval split)
python -m app.eval_runner --tier 1 --split eval \
  --conditions arm_a,hp,hp+sg,hp_ffmpeg,hp_wiener,hp_wiener_oa \
  --snrs none,0,5,10,20 --noise demand \
  --demand-envs DKITCHEN,DLIVING,DWASHING \
  --data-root /kaggle/input/acl6060 --demand-root /kaggle/input/demand \
  --out /kaggle/working/batches/tier1_eval --no-resume

# Tier 2 — M3AV, batched per duration bucket (notebook auto-discovers clip roots)
python - <<'PY'
from pathlib import Path
from types import SimpleNamespace
from app import eval_data, eval_runner

CONDITIONS = "arm_a,hp,hp+sg,hp_ffmpeg,hp_wiener,hp_wiener_oa"
BUCKETS = ["<5m", "5-10m", "10-20m", ">=20m"]

CLIP_ROOTS = sorted(
    str(p / "M3AV" / "extracted")
    for p in Path("/kaggle/input").iterdir()
    if p.is_dir() and (p / "M3AV" / "extracted").is_dir()
)
for clip_root in CLIP_ROOTS:
    for bucket in BUCKETS:
        selected = [c for c in eval_data.load_m3av_clips(clip_root) if eval_data.duration_bucket(c.duration_seconds) == bucket]
        if not selected:
            continue
        out_dir = "/kaggle/working/batches/tier2_" + bucket.replace("<", "lt_").replace(">", "gt_").replace("+", "p") + "_" + Path(clip_root).parent.parent.name
        orig = eval_runner.load_m3av_clips
        eval_runner.load_m3av_clips = lambda data_root=None, _sel=selected: _sel
        args = SimpleNamespace(tier="2", conditions=CONDITIONS, m3av_root=clip_root, data_root=None, out=out_dir, limit=None, resume=False)
        try:
            eval_runner.run_tier2(args)
        finally:
            eval_runner.load_m3av_clips = orig
        print(f"tier2 {Path(clip_root).name} bucket {bucket}: records -> {out_dir}")
PY
```

## Merge

```bash
python merge_eval_results.py --batch-dir /kaggle/working/batches --out /kaggle/working/final
```

Final outputs: `tier1_acl_results.{json,csv}`, `tier1_acl_summary.json`, `tier2_m3av_results.{json,csv}`, `tier2_m3av_summary.json`.

## Notes

- RTF / `seconds` are hardware-dependent (GPU here); never pool Kaggle RTF with local runs.
- Tier 1 and Tier 2 are reported separately and never pooled.
- Intermediates (`tier1_noise/`, `tier*_media/`) are transient by runner design (auto-deleted); keep only results + checkpoint in `/kaggle/working`.
- Checkpoint manifests already include device, compute type, threads, software versions, git commit.
