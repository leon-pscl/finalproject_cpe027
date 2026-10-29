# Evaluation Harness Guide

This guide explains how to use the Step 5A Evaluation Harness to generate noisy test sets for ASR evaluation.

## 🛠 Setup
Ensure you have the required dependencies installed:
```bash
pip install numpy soundfile pandas pyarrow
```

## 🚀 Running the Harness
The harness is controlled via `eval/harness/run_eval.py`. You can run it as a script or import it into a notebook.

### Option 1: Default Run
Runs the full matrix (All DEMAND environments $\times$ [0, 5, 10, 20] dB SNR) for both ACL and LoquaciousSet.
```bash
python eval/harness/run_eval.py
```

### Option 2: Custom Configuration (via Python)
To run a specific subset (e.g., only certain environments or SNR levels) to save time/space:

```python
from eval.harness.run_eval import run_harness

run_harness(
    snrs=[0, 10, 20],                # Target SNR levels in dB
    envs=['OOFFICE', 'STRAFFIC'],    # Environment keys from noise_bank.json
    output_dir=r"E:\EvalWork\test_run" 
)
```

## 📂 Outputs
- **Audio Files**: Saved to `E:\EvalWork\noisy_samples\`.
  - Naming convention: `{set}_{original_stem}_{env}_{snr}dB.wav`
- **Evaluation Manifest**: `eval/manifests/eval_harness_manifest.csv`.
  - Maps `original_path` $\rightarrow$ `noisy_path` $\rightarrow$ `text` $\rightarrow$ `environment` $\rightarrow$ `snr`.

## ⚠️ Notes
- **Read-Only**: The harness treats `E:\Datasets` as read-only.
- **LoquaciousSet**: Handled automatically via Parquet byte extraction.
- **ACL**: Only samples marked `is_clean=True` are used for controlled mixing.
