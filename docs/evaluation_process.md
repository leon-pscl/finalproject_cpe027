# ASR Evaluation Process Documentation

This document details the methodology, data requirements, and interpretation of results for the ASR (Automatic Speech Recognition) evaluation pipeline.

## 🔍 Evaluation Steps & Objectives

The evaluation is divided into three primary phases to determine how the model handles varying levels of acoustic degradation.

### 1. Baseline Clean Evaluation
- **What it determines**: The model's "ceiling" performance under ideal conditions.
- **Why**: To establish a ground‑truth accuracy level. If the model fails here, noise‑robustness is irrelevant. It isolates the model's linguistic and acoustic capabilities from environmental interference.

### 2. Tier 1: Controlled Noise Mixing
- **What it determines**: The model's sensitivity to specific types of noise and the exact point of failure (the "breaking point") relative to Signal‑to‑Noise Ratio (SNR).
- **Why**: By using a fixed noise bank (DEMAND), we can scientifically measure how much noise a model can tolerate before the Word Error Rate (WER) spikes. This allows for precise comparison between different model versions.

### 3. Tier 2: Real‑World Noisy Evaluation
- **What it determines**: The model's generalizability to organic, uncurated noise.
- **Why**: Synthetic mixing (Tier 1) is a proxy. Real‑world recordings contain unpredictable noise transients, overlapping speakers, and reverb that synthetic mixing may not fully replicate. This validates the synthetic results against reality.

---

## 📚 Dataset Requirements & Preprocessing

| Eval Step | Datasets Used | Why it is needed | Preprocessing Applied |
| :--- | :--- | :--- | :--- |
| **Baseline** | ACL 60/60 (Clean), LoquaciousSet | To provide high‑quality reference audio and text. | **Loquacious Standard**: Uppercase, no punctuation, numerals converted to words. |
| **Tier 1** | Clean Sources + DEMAND Noise Bank | To create a matrix of synthetic noisy samples. | **SNR Scaling**: Noise is scaled to target dB; **Tiling**: Noise is looped to match signal length; **Peak Norm**: Prevents clipping. |
| **Tier 2** | ACL 60/60 (Noisy) | To test against actual environmental recordings. | **Filtering**: Only samples marked `is_clean=False` are extracted to serve as the noisy test set. **Pre‑processing**: All audio is resampled to 16 kHz mono before evaluation. |

---

## 📈 Interpreting Evaluation Values

The primary metric used in this pipeline is **Word Error Rate (WER)**, supplemented by **Word Accuracy**.

### Word Error Rate (WER)
- **Formula**: $WER = \frac{Substitutions + Deletions + Insertions}{Total\ Reference\ Words}$
- **Value Meaning**:
    - **Lower is Better**: A WER of $0\%$ indicates a perfect transcription.
    - **Higher is Worse**: A high WER indicates the model is struggling to distinguish speech from noise.
- **Example**: If the reference is "THE CAT SAT" and the model says "THE MAT SAT", the WER is $33.3\%$ (1 substitution / 3 words).

### Word Accuracy
- **Formula**: $\frac{Correct\ Words}{Total\ Reference\ Words}$
- **Value Meaning**:
    - **Higher is Better**: $100\%$ accuracy means every word was correctly identified in the correct order.
    - **Lower is Worse**: Indicates a loss of precision.

### Performance Analysis Matrix
| Observation | Meaning |
| :--- | :--- |
| **Clean WER $\approx$ Noisy WER** | The model is highly robust to that specific noise type. |
| **WER increases as SNR $\downarrow$** | Expected behavior; the model's performance degrades as noise becomes louder. |
| **Tier 1 WER $\ll$ Tier 2 WER** | The model handles synthetic noise well but struggles with the complexity of real‑world recordings. |

## 🔧 Implementation Details

- **ASR**: The benchmark now uses the real Groq Whisper API via `backend.app.groq_asr`. The `ASRModelWrapper` in `eval/model_wrapper.py` reads `GROQ_API_KEY` from the environment (via `backend.app.config`) and calls the Groq endpoint, returning a genuine transcription string.
- **RAG**: The pipeline relies on `OpenAIAnswerGenerator` (`backend/app/answer_generator.py`), which calls OpenAI's Chat Completion API (`gpt-4o-mini`). It requires `OPENAI_API_KEY` to be set.
- **Required Environment Variables**:
  - `GROQ_API_KEY` – Groq token for Whisper transcription.
  - `OPENAI_API_KEY` – OpenAI token for ChatGPT.
  - `WHISPER_MODEL` (optional) – Whisper model size (`small`, `base`, etc.) used by Groq; defaults to `small`.

Make sure both keys are present before running `run_harness.py`, `run_benchmark.py`, or the demo script.
