# Evaluation Harness Guide

This guide explains how to use the **Step 5A Evaluation Harness** to generate a synthetic noisy test set for ASR evaluation, and how to run the benchmark that uses the real Groq Whisper API and OpenAI RAG pipeline.

---

## 🛠 Setup

Make sure you have the required Python packages.  In addition to the original dependencies we now require **librosa** for resampling:

```bash
pip install -r requirements.txt   # includes numpy, soundfile, pandas, pyarrow, librosa, etc.
```

The project reads configuration (including the **GROQ_API_KEY** and **OPENAI_API_KEY**) from the `.env` file in the repository root, so no extra steps are needed as long as those keys are present.

---

## 🚀 Running the Harness (mixing clean audio with DEMAND noise)

The harness is now invoked via a tiny wrapper script (`run_harness.py`) that takes care of package imports, caching, resume support, and reliable file writes.

### Option 1️⃣ Default Run (recommended)

Generate the complete matrix (all DEMAND environments × [0, 5, 10, 20] dB) for both the ACL and LoquaciousSet datasets:

```bash
python run_harness.py
```

- **Resume support** – If you stop the process, simply rerun the command; already‑processed `(original_path, environment, snr)` combos are skipped.
- **Output** – Noisy WAV files are written to `E:\EvalWork\noisy_samples\` and a manifest `eval/manifests/eval_harness_manifest.csv` is (re)created.

### Option 2️⃣ Custom Configuration (via Python)

For fine‑grained control you can import `run_harness` directly:

```python
from eval.harness.run_eval import run_harness

run_harness(
    clean_manifests={
        "acl": "eval/manifests/acl_manifest.csv",
        "loq": "eval/manifests/loq_manifest.csv",
    },
    snrs=[0, 10, 20],                 # target SNR levels (dB)
    envs=["OOFFICE", "STRAFFIC"],   # subset of DEMAND environments
    output_dir=r"E:\EvalWork\my_subset",
)
```

---

## 📂 Outputs

| Artifact | Location | Description |
|---|---|---|
| **Noisy audio files** | `E:\EvalWork\noisy_samples\` (or the custom `output_dir` you provide) | Files are named `{set}_{original_stem}_{env}_{snr}dB.wav` and are all **16 kHz mono** (the harness resamples both clean and noise to a common rate). |
| **Evaluation manifest** | `eval/manifests/eval_harness_manifest.csv` | CSV with columns `original_path, noisy_path, text, environment, snr, set`. Used later by `run_benchmark.py`. |

---

## 📈 Running the Benchmark (real transcription & metrics)

After the noisy set is ready, evaluate it with the real ASR model (Groq Whisper) and compute Word‑Error‑Rate / accuracy:

```bash
python run_benchmark.py
```

The benchmark script:
1. Loads the manifest created by the harness.
2. Calls `ASRModelWrapper` (which now forwards the audio to Groq’s Whisper endpoint using the key from `.env`).
3. Concatenates segment texts into a plain‑text hypothesis.
4. Computes WER and word‑accuracy via `eval/metrics.py`.
5. Writes two CSV reports to `eval/reports/`:
   - `benchmark_results.csv` – per‑sample details.
   - `summary_report.csv` – mean WER/accuracy grouped by dataset, environment, and SNR.

> **Note** – The benchmark requires both `GROQ_API_KEY` (for Whisper) and `OPENAI_API_KEY` (used later by the RAG pipeline, e.g., in `scripts/demo.py`). Ensure they are present in `.env` before running.

---

## ⚙️ Implementation Details (what changed)

- **Chunked transcription** – `ASRModelWrapper` now automatically splits audio longer than 30 seconds into smaller chunks before sending them to Groq, preventing payload‑size errors.
- **Noise caching** – `NoiseMixer` now loads each environment’s noise file once, resamples it to 16 kHz mono, and caches the result for all subsequent mixes.
- **Resume / caching** – The harness reads an existing `eval_harness_manifest.csv` and skips any `(original_path, environment, snr)` that are already present.
- **Resampling** – Both clean audio (any original sample‑rate) and noise are resampled to a common **TARGET_SR = 16 kHz** using `librosa`. This eliminates mismatched‑rate errors.
- **Stable sequential processing** – We replaced the previous `ThreadPoolExecutor` with a simple sequential loop. This avoids memory pressure and Windows file‑handle conflicts (`WinError 32`).
- **Wrapper script** – `run_harness.py` lives at the repository root, imports `run_harness` from `eval.harness.run_eval`, and ensures the `eval` package is importable without the `-m` flag.
- **No dummy models** – `eval/model_wrapper.py` now calls the real Groq Whisper endpoint; the RAG pipeline already uses the real OpenAI ChatGPT (`gpt‑4o‑mini`).

---

## ⚠️ Notes & Best Practices

- **Read‑only source data** – The harness never writes to `E:\Datasets`; it only reads audio files.
- **ACL clean‑sample filtering** – Only rows with `is_clean=True` are mixed for ACL (ensuring a clean baseline).
- **LoquaciousSet handling** – Audio stored in Parquet is extracted as raw bytes and decoded automatically.
- **Environment variables** – The script relies on the `.env` file for API keys and for the following settings (you may keep the defaults):
  - `GROQ_API_KEY` – Groq Whisper token.
  - `OPENAI_API_KEY` – OpenAI token (used later by RAG).
  - `WHISPER_MODEL` (optional) – Whisper model id (`small` by default).
- **Processing mode** – The `.env` entry `PROCESSING_MODE=real` is already set, so the benchmark will hit the real APIs.

---

## 🎉 You’re ready!

1. Verify the `.env` contains valid keys.
2. Run `python run_harness.py` to create the noisy test set (resume works out‑of‑the‑box).
3. Run `python run_benchmark.py` to get WER/accuracy numbers.
4. (Optional) Use `scripts/demo.py` to see the full end‑to‑end pipeline with RAG note generation.

Happy evaluating!