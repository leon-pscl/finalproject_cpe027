# Coding-Agent Task Instructions v3: Full Pipeline on `iteration_pascual`

## Purpose and Precedence

This file replaces v2. The agent builds the whole pipeline (DSP -> ASR -> embedding -> RAG) on the owner's branch `iteration_pascual`. The owner verifies it there, then integrates it into `iteration1-merged`, and only then into `main` for deployment (no Firebase Hosting). `docs/instructions.md` (Rev 2.3) still defines architecture, contracts, security, DSP design, and the Evaluation Plan. This file overrides it only on the points under "Recorded Deviations". Log each deviation in `docs/decision-log.md` before implementing it.

## Recorded Deviations

1. Phases 1 and 2 are merged: build the backend foundation and the real pipeline together. Evaluation tuning and release hardening (Phases 3-4) follow later.
2. Cloud-hosted models are allowed for ASR, embeddings, and answer generation (local hardware is insufficient). `faster-whisper` on CPU is an optional adapter. Select providers by configuration only.
3. Input is pre-recorded uploads only; live or streaming transcription stays excluded.
4. The branch promotion path below replaces the "one branch per phase, stop at each phase boundary" rule. Stop points are the promotion gates instead.

All other rules in `instructions.md` stay: no fabricated results, no silent mocks in production, owner isolation, private bucket, deletion, no secrets committed, no model training, no second vector database.

## Branch Promotion Workflow

Path: `iteration_pascual` -> `iteration1-merged` -> `main` (deployed).

- **Work only on `iteration_pascual`.** Commit in small, labeled steps (one per Build Step). Do not push to `iteration1-merged` or `main`, and do not force-push any branch.
- **Before starting**, report the branch state: at last inspection `iteration_pascual` and `iteration1-merged` pointed to the same commit (`5d91b01`), while `main` was one commit ahead (`d2843a7`, message "6 7"), and `iteration_lim` and `iteration_bueno` held teammate work. Compare each branch against `main`, list differences, and ask the owner whether to merge `main` into `iteration_pascual` first. Do not merge or delete branches without approval.
- **Gate A (verified on `iteration_pascual`)**: all mandatory checks pass locally and in CI, and the end-to-end flow works with the real pipeline on an approved recording. The agent reports; the owner decides.
- **Gate B (integration in `iteration1-merged`)**: after the owner merges, the agent rebases or merges to resolve conflicts with the teammates' UI changes, re-runs the full check suite, and reports regressions. Do not resolve conflicts by discarding teammate work.
- **Gate C (promotion to `main`)**: only after Gate B passes and the owner approves. Confirm `main` builds, CI passes, mock mode is rejected for production, and no secrets are in the diff. Deployment to the target environment (no Firebase Hosting) needs separate owner approval.
- Because the pipeline reaches `main` in one large change, keep it behind flags (`PROCESSING_MODE=mock|real`, `ASR_PROVIDER`, `EMBED_PROVIDER`, `LLM_PROVIDER`, `DSP_ENABLED`) so a partial failure cannot break the live app. Preserve existing frontend behavior when the backend is unavailable or in mock mode.
- Keep the diff reviewable: avoid reformatting or restructuring files unrelated to the pipeline (for example, do not rewrite `App.tsx` wholesale). Large UI refactors increase Gate B merge conflicts with teammates.

## Operating Rules

1. Inspect before changing; report what you read. Extend working code; do not restructure without need.
2. Create `docs/development-plan.md`, `docs/phase-status.md`, `docs/decision-log.md`, and `docs/repo-audit.md` first.
3. Never invent results or report unexecuted checks as passed.
4. If credentials, billing, or provider access are missing, finish safe local work (interfaces, mocks, emulator tests) and document the blocked check.
5. Never delete data, rotate credentials, change billing, provision paid resources, or run destructive migrations without approval.
6. After each Build Step, post a handoff: changes, files, commands run with results, limitations, next step.

## Build Steps (commit each separately on `iteration_pascual`)

### Step 1: Audit, docs, foundation, CI
- Audit `frontend/src/` (`App.tsx`, `auth/`, `pages/`, `services/mock/`, `recording/`) and `backend/`; record what is mocked, what is real, and test status.
- Add `backend/app/config.py`, `contracts.py`, `firebase.py`, `auth.py`, `repositories.py`, and the adapter interfaces from `instructions.md`.
- Add `firebase/` (rules, indexes, emulator config) and `.env.example`; add CI with pinned versions (no model or dataset downloads in CI).

### Step 2: API, upload, job queue
- Endpoint table with signed uploads, stored-object verification, quotas, and stable error codes.
- Firestore transactional job claim with lease, heartbeat, bounded attempts, idempotent steps, deterministic job IDs, and visible stages.
- Tests: cross-user isolation, repeated `upload-complete` creates one job, lease recovery, over-limit rejection.

### Step 3: Frontend upload workflow
- Read `recording/`. If it only captures from the microphone, add a file-upload path with title and type/size/duration checks, progress, and status polling; the recorder stays optional.
- Add an API client behind the existing service interface, chosen by configuration; make minimal edits to existing UI files.
- Implement empty, loading, retryable-error, unsupported-file, expired-session, and no-evidence states with accessible announcements.

### Step 4: Media and DSP engine
- `MediaService`: ffprobe/FFmpeg through safe argument lists, timeouts, temp cleanup; reject files without audio.
- `AudioProcessor`: mono 16 kHz float32, zero-phase high-pass (start near 80-100 Hz), level normalization with clipping protection, optional conservative spectral gating, optional VAD with an offset map. Every stage is parameterized and individually bypassable; enhancement stages default to bypass until evaluation supports enabling them.
- Retain the original video and the normalized non-enhanced baseline (Arm A). Record DSP configuration, stage runtimes, and diagnostics per processing version. DSP runs on CPU in the worker.
- Unit tests on hand-written fixtures: silence, stereo, low volume, clipping, chunk boundaries, offset-map correctness.

### Step 5: ASR adapter
- `Transcriber` provider interface: hosted Whisper-class API by default, optional local `faster-whisper`. Keys stay server-side.
- Split long audio into overlapping chunks within provider limits and merge with the offset map so times follow the original timeline.
- Persist ordered segments; guard against looping text and non-speech hallucination. Record provider, model identifier/revision, decoding settings, language, and DSP configuration. Add timeouts, bounded retries, and per-user duration/cost budgets.
- Provider failure or silent audio fails safely with a stable error code; never fall back to fixture content.

### Step 5A: DSP Evaluation Harness (inserted before Step 6)
- Create `eval/` and `docs/evaluation-protocol.md` covering the design, datasets, normalization policy, metric definitions with denominators, key-term rule, non-speech selection rule, and decision rule from `instructions.md`.
- Dataset manifests for E1 M3AV, E2 ACL 60/60, E3 TED-LIUM 3, E4 Loquacious: verify licenses and transcript quality on a sample; record identifiers, splits, checksums, and sample counts. Commit manifests only, never audio or transcripts. No synthetic, noise-mixed, or project-recorded evaluation audio; the self-recorded lecture is excluded from every metric table.
- Freeze development and held-out subsets per set before any tuning; tune DSP parameters (for example high-pass cutoff, spectral-gating strength) on development subsets only.
- Freeze the key-term list per set by a documented rule applied to the reference transcripts, reviewed by a person (record the rule, list, and reviewer). Do not build or adjust it from any arm's output.
- Runner in `eval/`: for every recording, run the same `Transcriber` adapter and settings under each arm, writing machine-readable results:
  - Arm A: mono, 16 kHz, level normalization only.
  - Arm B: Arm A plus high-pass filter and optional conservative spectral gating.
  - Arm C (optional): Arm A plus one pretrained neural denoiser, context only.
  - Identical ASR provider, model identifier/revision/date, decoding settings, and language in every arm; only the audio processing changes.
- Metrics with one fixed normalization policy (casing, punctuation, numerals, contractions), pinned library versions (e.g. `jiwer`):
  - WER with S/D/I reported separately (rising deletions suggest over-suppression; rising insertions suggest hallucination).
  - CER.
  - Key-term error rate with denominator of reference term occurrences shown; report for a set only if counts are adequate.
  - Non-speech hallucination rate using only naturally occurring non-speech regions from reference timestamps, with a documented minimum duration and safety margin; report "not evaluable" where timestamps are unreliable. Also report inserted words per minute of non-speech audio and flag repeated-phrase looping.
  - DNSMOS P.835 (SIG, BAK, OVRL) on the audio each arm sends to the ASR; supplementary only, no pass/fail threshold.
  - RTF and DSP overhead per stage and in total, with hardware, CPU count, memory, and warm versus cold runs recorded. For a hosted ASR, also record latency and cost per audio minute.
- Conditions without synthetic degradation: compute per-recording diagnostics (SNR proxy, clipping fraction, silence fraction, RMS), group into pre-declared bins (clean, moderate, noisy), and report paired results per bin. State that this design cannot establish error rate as a function of controlled SNR.
- Statistics: delta (Arm A minus Arm B, positive means DSP helped for error metrics) with a paired bootstrap confidence interval resampled over recordings (or fixed-length segments for long-form audio), plus counts. Call a change "supported" only if the interval excludes zero. Report each set separately; do not pool sets.
- Metric scripts get unit tests on hand-written examples (unit-test fixtures only, never reported as performance evidence), plus a single command that regenerates every table from per-recording results.
- Run the development-subset comparison and write `docs/dsp-evaluation-results.md`: what changed, counts, intervals, failures, and the resulting default. Run held-out subsets once, after parameters are frozen, and disclose any contamination.

### 5A. Decision rule (apply, do not weaken)
- Enable a DSP stage by default only if it gives a supported WER improvement on development subsets for the target bins and does not regress, beyond a tolerance agreed with the owner, clean-bin WER, CER, key-term error rate, or non-speech hallucination rate.
- DNSMOS gains alone never justify enabling a stage.
- If a stage helps only in the noisy bin, make it conditional on measured diagnostics or leave it opt-in.
- A stage whose overhead exceeds the RTF/cost budget the owner sets after the first baseline stays disabled or opt-in.
- Until the owner sets numeric tolerances and freezes them, label results "measured comparisons", not "validated passes".

### 5A. Constraints and caveats the report must state
- Public sets may overlap with the ASR model's training data, which can lower baseline error and compress differences. Disclose per set.
- Results from public sets do not generalize to the deployment's own rooms and microphones.
- E4 clips are short and not lecture-specific; report E4 separately from E1-E3.
- With a hosted ASR, results are tied to the model version and date; rerun if the provider changes the model.
- Run evaluation locally or in a separately authorized workflow, not through the production worker, so it does not use application quotas. Watch hosted-ASR spend: estimate audio minutes (sets x arms) and get owner approval of the budget before the run.
- Never invent values, and never report an unexecuted run as completed.

### 5A. Problem statement (quoted on 2026-10-25)
"The (Mahirap mag-notes...)"; full verbatim text to be inserted into docs/evaluation-protocol.md when Step 5A begins.

### Step 6: Chunking, embeddings, vector index
- Overlapping, segment-aware chunks preserving segment IDs and time ranges; size, overlap, and retrieval count configurable.
- `Embedder` provider interface (hosted default, local optional). One model and one vector dimension per active index; reject incompatible query embeddings; model changes require an explicit reindex workflow.
- Firestore vector fields with the composite index in `firestore.indexes.json`. Verify prefilter behavior and dimension limits in current documentation at setup. Write chunks in batches.
- Vector queries run server-side only, filtered by owner, lecture, and active processing version before nearest-neighbor selection.

### Step 7: RAG answering and notes
- `Retriever` returns authorized evidence only. `AnswerGenerator` (hosted LLM through a provider interface) answers only from retrieved evidence, else `insufficient_evidence`; treat transcript text as untrusted and ignore instructions inside it.
- Validate every returned source ID against retrieved evidence; resolve timestamps and text server-side; never accept model-invented IDs, URLs, or timestamps.
- `NotesGenerator` produces source-linked notes; if it fails, transcript and Q&A still work. Activate a version only after validation; stale versions must not replace newer ones.
- Tests: malformed citations, empty retrieval, cross-chunk evidence, prompt injection inside a transcript, cross-user retrieval via the worker path.

### Step 8: Worker wiring, exports, deletion
- Worker pipeline: validate -> extract -> DSP -> ASR -> segments -> chunks -> embeddings -> notes -> ready, resumable and idempotent (no duplicate segments or embeddings).
- TXT/VTT and Markdown exports, source-click video seeking, and deletion across Storage, jobs, segments, chunks/vectors, notes, and Q&A history.

### Step 9: Verification report (Gate A)
- Run the full check suite and an end-to-end run on an approved recording. Write `docs/pipeline-report.md`: executed versus unexecuted checks, measured RTF, latency, cost per audio minute, peak memory, supported languages, and limitations.
- Stop. Report to the owner for Gate A. Do not touch `iteration1-merged` or `main`.

## Evaluation (after Gate A; separate from production)

- Public datasets only (E1 M3AV, E2 ACL 60/60, E3 TED-LIUM 3, E4 Loquacious); manifests only, no committed audio. The self-recorded lecture is demonstration-only and never appears in a metric table.
- Paired design (Arm A baseline; Arm B conservative DSP; optional Arm C neural denoiser) with identical ASR provider, model, settings, and one fixed normalization policy.
- Report WER (S/D/I), CER, key-term error rate, non-speech hallucination rate, DNSMOS (supplementary), and RTF, with paired bootstrap intervals. Enable a DSP stage by default only under the decision rule in `instructions.md`.
- For hosted ASR, record the model identifier and run date, since hosted models can change. Run evaluation locally or in a separately authorized workflow.

## Security and Privacy

- Enforce owner isolation across metadata, storage, transcripts, embeddings, retrieval, exports, and Q&A history; derive the owner from the verified token `uid` only.
- Provider keys and service-account credentials stay server-side and out of the repository and logs. Run secret scanning on every diff, including before Gates B and C.
- Hosted providers receive audio and transcript text: disclose this, obtain the speaker's consent, and log the provider and its data-handling terms in `docs/decision-log.md`.
- Do not log lectures, questions, tokens, or signed URLs.

## Handoff

Each step: scope, changed files, exact commands and result summaries, deployment status, limitations, unresolved approvals, and next step.

**Start now:** report the branch comparison, then do Step 1 on `iteration_pascual`. Do not begin Step 2 until the owner reviews Step 1.

## References

- A. Radford et al., "Robust Speech Recognition via Large-Scale Weak Supervision," in *Proc. ICML*, PMLR vol. 202, 2023.
- Remaining academic references (R2-R9, D1-D4) are as listed in `docs/instructions.md`; verify bibliographic details before submission.
- Platform documentation (Firebase, Cloud Run, provider APIs) and pricing are non-academic; verify at setup time.
