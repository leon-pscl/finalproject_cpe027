# DSP Evaluation Harness

This directory contains the scaffolding for the two‑tier DSP evaluation described in `docs/step5A_dsp_evaluation_insert.md`. It includes dataset manifests, metric utilities, mixing scripts, arm builders, signal‑metric wrappers, a runner, and a reporting tool.

All heavy dependencies (e.g., `jiwer`, `pesq`, `pystoi`, `torchmetrics`, `onnxruntime`) are listed in `requirements.txt` and are **not** part of the main backend requirements.
