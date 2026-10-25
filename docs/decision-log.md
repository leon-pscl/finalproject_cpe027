# Decision Log

Each entry records a deviation from `docs/instructions.md` Rev 2.3, as required by `docs/agent_tasks_v3_pascual_branch.md`.

## 2026-10-25 — Branch and promotion workflow
- Deviation: single branch promotion path (`iteration_pascual` -> `iteration1-merged` -> `main`) replaces "one branch per phase, stop at phase boundary".
- Why: owner wants full pipeline on one branch, promotion gates instead.
- How applied: work only on `iteration_pascual`, small labeled steps, stop at Gate A.
- Owner decisions: do not merge `main` into `iteration_pascual` this pass; keep pushed stray commit `fc8a926` ("idk", package-lock only).

## 2026-10-25 — Phases 1 and 2 merged
- Deviation: build backend foundation and real pipeline together (Phase 3-4 later).
- Why: v3 recorded deviation 1.
- How applied: Steps 1-9 as defined in `docs/agent_tasks_v3_pascual_branch.md`.

## 2026-10-25 — Cloud-hosted models allowed
- Deviation: ASR/embeddings/answer generation may be cloud-hosted; faster-whisper on CPU is optional adapter; providers selected by configuration only.
- Why: local hardware insufficient.
- How applied: adapters behind `PROCESSING_MODE`/`*_PROVIDER` settings; `Real*` stubs fail clearly when unconfigured.

## 2026-10-25 — Pre-recorded uploads only
- Deviation: no live/streaming transcription.
- Why: v3 recorded deviation 3.

## 2026-10-25 — Insert Step 5A DSP evaluation harness
- Change: inserted `### Step 5A` between Step 5 (ASR) and Step 6 (chunking/embeddings/vector index) in `docs/agent_tasks_v3_pascual_branch.md`; renumbered via label only.
- Why: DSP-vs-no-DSP must be measured before indexing is built on top of it; null/negative result keeps bypass default.
- Removed: run-DSP-comparison paragraph concept from post-Gate-A evaluation (comparison moved to Step 5A); rest of Evaluation section retained as reference.
- `docs/step5A_dsp_evaluation_insert.md` kept as source record.
- Problem-to-be-solved wording: owner supplied 2026-10-25; to be quoted verbatim in `docs/evaluation-protocol.md` at Step 5A.

## 2026-10-25 — Safe local operating mode
- Deviation: first passes assume no cloud credentials, billing, region, datasets, providers.
- Why: owner chose safe local execution; credentials unconfirmed.
- How applied: foundation uses mocks/emulator + local FFmpeg; hosted work only in separately authorized workflow; reject mock mode in production.

## Rules retained unchanged
- No fabricated results, no silent mocks in production, owner isolation, private bucket, deletion, no committed secrets, no training, no second vector DB.