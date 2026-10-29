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

## 2026-10-25 — Merge conflict markers repaired before continuing
- Deviation: instead of continuing on top of the merge, the first task was repairing conflict markers that `278f551` and merge commit `a8df037` had committed.
- Why: `backend/app/main.py` did not import (`SyntaxError`), `config.py` had two `Settings` classes, `requirements.txt` and `frontend/src/services/api.ts` were unusable, so nothing after the merge could be verified.
- How applied: `a467340` — union merge for `main.py`/`requirements.txt`/`api.ts`; field-level merge for `config.py` keeping the owner's `max_upload_mb=512` and the `ENHANCE_AUDIO`/`TRANSCRIBE_WORKERS` env names; `585ced7` brings `ruff check`/`ruff format` (the `ci.yml` gate) back to pass.

## 2026-10-25 — One DSP switch: `media.py` in the pipeline, `dsp.py` evaluation-only
- Deviation: `enhance_default` now defaults to `false` (env `ENHANCE_AUDIO`, compose `${ENHANCE_AUDIO:-false}`), so `dsp.py` enhancement is only reachable from `app.evaluate` or an explicit `enhance` value on `POST /api/transcriptions`.
- Why: two DSP implementations were live at once; only `media.py` implements the Step 4 contract (Arm A baseline, per-stage bypass, per-stage runtimes, diagnostics), and a second pass would double-count its effect.
- How applied: the upload pipeline runs `LocalMediaService.validate_and_extract` once and calls `transcribe_file(..., enhance=False)`.

## 2026-10-25 — Upload pipeline worker runs in-process behind `WORKER_ENABLED`
- Deviation: partial Step 8 (worker wiring) executed before Step 5A and Steps 6-7, at the owner's direct request ("users upload a recording, then the DSP processes it").
- Why: `upload_complete` created jobs nothing consumed, so the upload path was a dead end; no separate worker process exists yet.
- How applied: `backend/app/worker.py` + FastAPI lifespan; `worker_enabled` (env `WORKER_ENABLED`, default true, forced false in `backend/tests/conftest.py`); claim -> validate -> preprocess -> transcribe -> completed/failed with a lease and heartbeat; stage, DSP configuration/runtimes/diagnostics and ASR metadata in `JobDocument.timings`; transcript written to `users/{owner}/{lecture}/transcript.json`.
- Known limits (recorded, not hidden): `FirestoreLectureRepository.list_all_lectures()` returns `[]`, so a Firestore deployment needs a queued-jobs query (comment in `worker.py`); media temp outputs are not deleted on success (same behavior as the existing `POST /api/transcriptions` flow); chunks/embeddings/notes stages are not wired.

## Rules retained unchanged
- No fabricated results, no silent mocks in production, owner isolation, private bucket, deletion, no committed secrets, no training, no second vector DB.