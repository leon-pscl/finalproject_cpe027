# Step 5A (v2): Two-Tier DSP Evaluation Harness

Branch base: `iteration_pascual`. Work on a feature branch off it (e.g. `feature/step5a-eval`). Do not push, merge, or open a PR without owner approval. Do not modify `main` or `iteration1-merged`.

## Operating rules
1. Inspect before editing. Extend existing code (`backend/app/evaluate.py`, `media.py`, `dsp.py`, `asr.py`, `config.py`) instead of replacing it silently.
2. Never invent results, and never report an unexecuted run as passed. Mark unrun items "not run".
3. No model training. No synthetic data outside the Tier 1 design below. Hand-written fixtures are for unit tests only and never count as performance evidence.
4. Do not commit audio, transcripts, mixes, or model weights. Commit manifests, scripts, and result tables only.
5. Do not download datasets, call a paid ASR, or change billing without owner approval. Estimate audio minutes (sets x arms x tiers) and get the budget approved first.
6. Record every deviation in `docs/decision-log.md` and update `docs/phase-status.md` at handoff.
7. Stop for owner review after Task 5A.14, before Step 6.

## Question
Does adding the DSP layer before the same pretrained ASR reduce transcription errors on lecture audio, and under which conditions does it help, do nothing, or harm? Quote the project's problem statement from the repo documents in `docs/evaluation-protocol.md`; if none exists, stop and ask the owner.

## Existing code facts (verified on the branch; re-check before relying on them)
- `backend/app/media.py` is the pipeline DSP: Arm A (16 kHz mono loudnorm), 80 Hz zero-phase high-pass, optional spectral gating, VAD bounding. Controlled by `DSP_ENABLED` (default false).
- `backend/app/dsp.py` is a separate Wiener + dereverberation enhancer, currently used only by `app.evaluate` and by `transcribe_file(enhance=True)`.
- `backend/app/evaluate.py` is a single-recording CLI with its own `normalize`/`wer`/`cer`/`term_accuracy` (rapidfuzz).
- `backend/app/asr.py` runs faster-whisper with `vad_filter=True`, `condition_on_previous_text=False`, and drops segments with `no_speech_prob > 0.8`. `asr_provider="groq"` routes to `groq_asr.py`.
- Evaluation code must call `transcribe_file(..., enhance=False)` on audio that the harness has already processed, so the arm definitions below are the only DSP applied.

## Arms (identical ASR provider, model, revision/date, decoding settings, language)
- Arm A (baseline): `media.py` with `DSP_ENABLED=false` (mono, 16 kHz, loudness normalization with clipping protection).
- Arm B (project DSP): `media.py` with `DSP_ENABLED=true` (adds the high-pass and optional spectral gating). Ablate each stage separately.
- Arm C (classical comparison): `dsp.enhance()` Wiener + dereverberation applied to Arm A audio, for context.
- Arm D (optional): one pretrained neural denoiser, for context only. Skip unless the owner approves.
- Tier 1 only: Arm Clean (original clean audio through Arm A, the upper bound) and Arm B-on-clean (clean audio through Arm B, the do-no-harm check).

## Tiers and datasets
Tier 1, controlled (simulated). Clean reference speech: the cleanest recordings from E2 (ACL 60/60) and E3 (TED-LIUM 3 manually transcribed dev/test). Choose them by a documented rule using DNSMOS BAK and the SNR proxy on the originals, not by listening. Noise: DEMAND (CC BY-SA 3.0, check the terms) and the noise portion of MUSAN. SNR grid: 20, 10, 5, 0, -5 dB (freeze before any run). Mixing is deterministic: seeded noise selection, random onset, level set from active-speech RMS, clipping protection. Add reverberation only from existing recorded room impulse responses, and label it simulated. Never redistribute mixes.

Tier 2, real recordings (no added noise): E1 M3AV (primary), E2 ACL 60/60, E3 TED-LIUM 3 dev/test, E4 Loquacious dev/test. Verify each licence and the provenance of each reference transcript on a sample. M3AV dev/test references are reported to be a manual combination of Whisper and Microsoft STT output, so check a sample for bias toward Whisper and disclose it. Use only manually transcribed TED-LIUM 3 dev/test talks. Report E4 separately (short clips, not lecture-specific).

The self-recorded demo lecture is excluded from every table.

## Metrics
All use one fixed normalization policy (casing, punctuation, numerals, contractions) applied identically to references and hypotheses, with pinned library versions.
- WER with S/D/I rates, and CER (Tiers 1, 2).
- Key-term error rate: frozen term list per set from a documented rule applied to the reference transcripts, reviewed by a person; show the denominator; report only where counts are adequate (Tiers 1, 2).
- Non-speech hallucination rate: natural gaps from reference timestamps only, with a documented minimum duration and safety margin; also inserted words per minute and repeated-phrase flag; "not evaluable" where timestamps are unreliable; not for E4 (Tiers 1, 2).
- DNSMOS P.835 SIG/BAK/OVRL on the audio each arm sends to the ASR; supplementary, no threshold (Tiers 1, 2).
- SI-SDR improvement, PESQ wideband, STOI/ESTOI against the clean reference (Tier 1 only).
- RTF and DSP overhead per stage and in total; record hardware, CPU count, memory, warm vs cold; for hosted ASR also latency and cost per audio minute (Tiers 1, 2).
- Per-recording diagnostics for binning (Tier 2): SNR proxy, clipping fraction, silence fraction, RMS. Pre-declare bin edges before any run.

## Statistics
Per tier, set, and bin (Tier 1: per SNR level and noise type): delta = Arm A minus Arm B (positive means DSP helped for error metrics), with a paired bootstrap confidence interval resampled over recordings (or fixed-length segments for long-form audio), plus counts. Also report relative WER reduction and the largest per-item regressions. A change is "supported" only if the interval excludes zero. Never pool sets or tiers. State that Tier 2 cannot establish error as a function of controlled SNR, and that Tier 1 noise is simulated.

## Tasks
- [ ] 5A.1 Create `eval/` (`eval/README.md`, `eval/requirements.txt`, `eval/manifests/`, `eval/results/` git-ignored) and `docs/evaluation-protocol.md` (design, arms, datasets, normalization policy, metric definitions with denominators, key-term and non-speech rules, bins, decision rule). Keep heavy dependencies (jiwer, pesq, pystoi, torchmetrics, onnxruntime for DNSMOS) out of `backend/requirements.txt`.
- [ ] 5A.2 Dataset manifests only: identifiers, splits, checksums, counts, licence, and reference provenance for E1-E4 and the noise sources. Add `.gitignore` entries for media, transcripts, and mixes. Flag the `.wav` files already committed under `backend/` to the owner; do not delete them.
- [ ] 5A.3 Freeze development and held-out subsets per set before any tuning. Tune DSP parameters (high-pass cutoff, spectral-gating strength) on development subsets only.
- [ ] 5A.4 Freeze key-term lists (rule, list, reviewer recorded). Do not build or adjust them from any arm's output.
- [ ] 5A.5 Shared metrics module `eval/metrics.py` (normalization, WER/CER with S/D/I, KTER, NSHR). Refactor `backend/app/evaluate.py` to import it or mark it legacy; do not break its CLI without logging the change. Unit tests on hand-written examples only.
- [ ] 5A.6 Tier 1 mixer `eval/mix.py`: deterministic, seeded, SNR computed on active speech, writes mixes to git-ignored storage with a manifest of seed, noise file, SNR, onset.
- [ ] 5A.7 Arm builders `eval/arms.py` that produce Arm A, B (with per-stage ablations), C, and the Tier 1 clean arms as WAV files by calling `media.py` and `dsp.py`, recording stage runtimes.
- [ ] 5A.8 Signal-metric module `eval/signal_metrics.py`: SI-SDR improvement, PESQ, STOI/ESTOI (Tier 1) and DNSMOS wrapper (both tiers). Pin versions and the DNSMOS model files; do not commit weights.
- [ ] 5A.9 Runner `eval/run.py`: for every item and arm, call `transcribe_file(path, enhance=False)` with identical settings, write per-item CSV/JSON (set, tier, arm, bin or SNR, every metric, runtimes, hardware). Support resume and a `--dry-run` that estimates audio minutes and ASR cost.
- [ ] 5A.10 Diagnostics and binning for Tier 2 using pre-declared bin edges.
- [ ] 5A.11 Statistics `eval/report.py`: paired bootstrap, relative reduction, tables per tier/set/bin/SNR, worst-regression list, and one command that regenerates every table from the per-item results.
- [ ] 5A.12 CI: add `eval/` to `ruff check` and `ruff format --check`, and run the metric unit tests. CI must not download datasets, models, or call an ASR.
- [ ] 5A.13 Development-subset run (owner-approved budget). Write `docs/dsp-evaluation-results.md`: counts, intervals, failures, regressions, the recommended default. Run held-out subsets once after parameters are frozen and disclose any contamination.
- [ ] 5A.14 Update `docs/phase-status.md`, `docs/decision-log.md`, and `docs/development-plan.md`. Report executed commands, results, unrun items, and blockers. Stop for owner review.

## Decision rule (apply, do not weaken)
- Enable a DSP stage by default only if it gives a supported WER improvement on development subsets for the target bins/SNRs and does not regress, beyond an owner-agreed tolerance, clean-bin WER, CER, KTER, or NSHR.
- DNSMOS, SI-SDR, PESQ, or STOI gains alone never justify enabling a stage.
- If a stage helps only at low SNR or in the noisy bin, make it conditional on measured diagnostics or leave it opt-in.
- A stage whose overhead exceeds the owner's RTF/cost budget stays disabled or opt-in.
- Until the owner freezes numeric tolerances, label results "measured comparisons", not "validated passes".

## Caveats the report must state
- Public sets may overlap with the ASR model's training data and can compress differences. Disclose per set.
- Tier 1 noise is simulated and the "clean" source is not studio-clean; Tier 2 cannot isolate noise as the only variable.
- Results do not generalize to the deployment's own rooms and microphones.
- E4 clips are short and not lecture-specific.
- With a hosted ASR, results are tied to the model version and date.
- Run evaluation locally or in a separately authorized workflow, not through the production worker.

## Handoff
Deliverables: `docs/evaluation-protocol.md`, manifests, frozen key-term lists, `eval/` scripts, per-item results, `docs/dsp-evaluation-results.md`. State the recommended DSP default with evidence, then stop.