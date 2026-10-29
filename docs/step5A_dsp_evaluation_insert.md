# Insert for Instructions v3: Step 5A, DSP Evaluation Harness (after Step 5, before Step 6)

## Where it goes

Insert this section into `agent_tasks_v3_pascual_branch.md` between Step 5 (ASR adapter) and Step 6 (chunking, embeddings, vector index). Renumber later steps or call it "Step 5A". Remove the "Evaluation (after Gate A)" paragraph about running the DSP comparison later; keep the rest of that section as the reference for design and metrics. Log the change in `docs/decision-log.md`.

## Why here

DSP and ASR now both exist, and everything downstream (chunking, embeddings, RAG) depends on the audio the ASR receives and the transcript it returns. The DSP-versus-no-DSP result decides which processing configuration becomes the default, so it must be measured before indexing is built on top of it. A null or negative result is valid: if DSP does not help, the default stays bypass and the project reports that finding.

## Question being answered

State the project's problem-to-be-solved exactly as written in the project documents (quote it in `docs/evaluation-protocol.md`; if no statement exists in the repository, stop and ask the owner for it). Then restate it as a testable question: *Does adding the DSP layer before the same pretrained ASR reduce transcription errors on lecture-type audio, and under which recording conditions does it help, do nothing, or harm?*

## Tasks

- [ ] 5A.1 Create `eval/` and `docs/evaluation-protocol.md` covering the design, datasets, normalization policy, metric definitions with denominators, key-term rule, non-speech selection rule, and decision rule from `instructions.md`.
- [ ] 5A.2 Dataset manifests. Use existing public datasets with human references only (E1 M3AV, E2 ACL 60/60, E3 TED-LIUM 3, E4 Loquacious). Verify each license and transcript quality on a sample; record identifiers, splits, checksums, and sample counts. Commit manifests only, never audio or transcripts. No synthetic, noise-mixed, or project-recorded evaluation audio; the self-recorded lecture is excluded from every metric table.
- [ ] 5A.3 Freeze development and held-out subsets per set before any tuning. Tune DSP parameters (for example the high-pass cutoff and spectral-gating strength) on development subsets only.
- [ ] 5A.4 Freeze the key-term list per set by a documented rule applied to the reference transcripts, reviewed by a person (record the rule, list, and reviewer). Do not build or adjust it from any arm's output.
- [ ] 5A.5 Runner. A script in `eval/` that, for every recording, runs the same `Transcriber` adapter and settings under each arm and writes machine-readable results:
  - Arm A: mono, 16 kHz, level normalization only.
  - Arm B: Arm A plus high-pass filter and optional conservative spectral gating.
  - Arm C (optional): Arm A plus one pretrained neural denoiser, for context only.
  - Each arm uses the identical ASR provider, model identifier, revision/date, decoding settings, and language. Only the audio processing changes.
- [ ] 5A.6 Metrics, one fixed normalization policy (casing, punctuation, numerals, contractions) applied identically to references and hypotheses, pinned library versions (for example `jiwer`):
  - WER with substitution, deletion, and insertion rates reported separately (rising deletions suggest over-suppression; rising insertions suggest hallucination).
  - CER.
  - Key-term error rate, with the denominator of reference term occurrences shown; report it for a set only if the counts are adequate.
  - Non-speech hallucination rate, using only naturally occurring non-speech regions from reference timestamps, with a documented minimum duration and safety margin; report "not evaluable" where timestamps are unreliable. Also report inserted words per minute of non-speech audio and flag repeated-phrase looping.
  - DNSMOS P.835 (SIG, BAK, OVRL) on the audio each arm sends to the ASR; supplementary only, with no pass/fail threshold.
  - RTF and DSP overhead per stage and in total, with hardware, CPU count, memory, and warm versus cold runs recorded. For a hosted ASR, also record latency and cost per audio minute, since RTF alone does not describe provider time.
- [ ] 5A.7 Conditions without synthetic degradation. Compute per-recording diagnostics (SNR proxy, clipping fraction, silence fraction, RMS), group recordings into pre-declared bins (for example clean, moderate, noisy), and report paired results per bin. State that this design cannot establish error rate as a function of controlled SNR.
- [ ] 5A.8 Statistics. For each set and bin report the delta (Arm A minus Arm B, positive means DSP helped for error metrics) with a paired bootstrap confidence interval resampled over recordings (or fixed-length segments for long-form audio), plus counts. Call a change "supported" only if the interval excludes zero. Report each set separately; do not pool sets.
- [ ] 5A.9 Metric scripts get unit tests on hand-written examples (unit-test fixtures only, never reported as performance evidence), plus a single command that regenerates every table from the per-recording results.
- [ ] 5A.10 Run the development-subset comparison and write `docs/dsp-evaluation-results.md`: what changed, counts, intervals, failures, and the resulting default. Run held-out subsets once, after parameters are frozen, and disclose any contamination.

## Decision rule (apply, do not weaken)

- Enable a DSP stage by default only if it gives a supported WER improvement on development subsets for the target bins and does not regress, beyond a tolerance agreed with the owner, clean-bin WER, CER, key-term error rate, or non-speech hallucination rate.
- DNSMOS gains alone never justify enabling a stage.
- If a stage helps only in the noisy bin, make it conditional on measured diagnostics or leave it opt-in.
- A stage whose overhead exceeds the RTF/cost budget the owner sets after the first baseline stays disabled or opt-in.
- Until the owner sets numeric tolerances and freezes them, label results "measured comparisons", not "validated passes".

## Constraints and caveats the report must state

- Public sets may overlap with the ASR model's training data, which can lower baseline error and compress differences. Disclose per set.
- Results from public sets do not generalize to the deployment's own rooms and microphones.
- E4 clips are short and not lecture-specific; report E4 separately from E1-E3.
- With a hosted ASR, results are tied to the model version and date; rerun if the provider changes the model.
- Run evaluation locally or in a separately authorized workflow, not through the production worker, so it does not use application quotas. Watch hosted-ASR spend: estimate audio minutes (sets × arms) and get owner approval of the budget before the run.
- Never invent values, and never report an unexecuted run as completed.

## Output and handoff

Deliverables: `docs/evaluation-protocol.md`, manifests, frozen key-term lists, per-recording results (CSV/JSON with set, arm, bin, and every metric), the regeneration script, and `docs/dsp-evaluation-results.md`. The handoff states the recommended DSP default with its evidence, then stops for owner review before Step 6 starts. Step 6 uses the chosen configuration.

## References

- A. Radford et al., "Robust Speech Recognition via Large-Scale Weak Supervision," in *Proc. ICML*, PMLR vol. 202, 2023.
- C. K. A. Reddy, V. Gopal, and R. Cutler, "DNSMOS P.835: A Non-Intrusive Perceptual Objective Speech Quality Metric to Evaluate Noise Suppressors," in *Proc. IEEE ICASSP*, 2022, pp. 886-890.
- T. Ochiai et al., arXiv:2404.14860, 2024 (preprint); arXiv:2512.17562, 2025 (preprint; authors and title to be verified); and arXiv:2501.11378, 2025 (preprint; authors to be verified). All three come from `docs/instructions.md`; verify before submission.
