# Phase Status

## Current position
- Branch: `iteration_pascual` (local only — `origin/iteration_pascual` is still at `fe0598f`, so nothing has been pushed this pass; the merge repair, the style pass, the worker and this doc update are all local).
- Promotion path: `iteration_pascual` -> `iteration1-merged` -> `main`.
- Operating mode: safe local (no cloud credentials assumed; hosted runs separately authorized).
- Active build step: owner-requested upload -> DSP -> ASR wiring is done locally (partial Step 8, executed before Step 5A by owner request); Step 5A scaffolded (eval/ package ready), Steps 6, 7, 9 not started.
- Blocked pending owner: push of the 7 local commits, faster-whisper model download (`MODEL_CACHE_DIR`) on first real run, Step 5A dataset/ASR budget.

## Step 1 progress
- [x] Repo audit (`docs/repo-audit.md`).
- [x] Development plan (`docs/development-plan.md`).
- [x] Decision log (`docs/decision-log.md`).
- [x] Insert Step 5A into task list (`docs/agent_tasks_v3_pascual_branch.md`).
- [x] Backend foundation modules.
- [x] Firebase rules, indexes, emulator config.
- [x] `.env.example`.
- [x] CI workflow.
- [x] Local verification.

## Step 1 verification
- Backend import/compile: passed (`python -m compileall backend/app backend/tests`).
- Ruff: passed (`ruff check backend`, `ruff format --check backend`).
- Backend tests: passed (`pytest` in `backend/`, 8 tests).
- Frontend lint: passed.
- Frontend build/typecheck: passed.
- Frontend tests: failed (2 tests in `src/App.test.tsx` because the initial route now requires login and renders the sign-in page). This failure reproduces on the stashed clean tree before Step 1 changes, so it is pre-existing and not introduced by this step; the other 6 frontend tests pass.
- Firebase emulator rules/integration: not run (Java and `firebase-tools` unavailable); not reported passed.
- Secret scan: manual diff review only; no secrets or credential files added.

## Step 2 progress
- [x] Backend-portable lecture/job repositories (`LectureRepository`, in-memory, Firestore, default).
- [x] Deterministic lecture-scoped job IDs and required stage/state values.
- [x] Firestore transactional claim, lease, heartbeat, bounded attempts, and retry support.
- [x] Artifact storage adapter with HMAC/local signed uploads and server-side object verification.
- [x] Upload initiation, stored-object verification, lecture/job quotas, and stable error codes.
- [x] FastAPI upload, list, get, upload-complete, retry, and storage endpoints.
- [x] Cross-user isolation and repeated upload-complete idempotence tests.
- [x] Lease recovery and over-limit tests.
- [x] Local verification after final storage content-type tightening.

## Step 2 verification
- Ruff: passed (`ruff check backend`, `ruff format --check backend`).
- Backend tests: passed (`pytest` in `backend/`, 12 tests).
- Storage robustness check: passed after tightened local content-type enforcement.
- Firestore emulator integration: not run (Java and `firebase-tools` unavailable); Firestore path remains implemented but not live-verified.
- Real provider/container checks: not run (safe local mode).

## Step 4 progress
- [x] Backend media/DSP module (`backend/app/media.py`) hardened for local processing.
- [x] FFmpeg availability verified (`ffmpeg version 8.1.2-full_build-www.gyan.dev`).
- [x] DSP configuration defaults: mock/safe local mode, `DSP_ENABLED=false`, bypass by default; Arm A 16 kHz mono loudnorm extraction always runs before any enhancement.
- [x] Extracted enhancement stages now explicitly standardize channels/sample rate and use a zero-phase 80 Hz high-pass chain (`highpass=f=...,areverse,highpass=f=...,areverse`).
- [x] Optional spectral gating, VAD bounding, and audio-duration guard are implemented in the media module; Arm A output remains the bypass behavior baseline.
- [x] WAV parsing hardened for RIFF/WAVE and IEEE-float PCM; nonfinite samples are rewritten to zeros and reparsed before diagnostics.
- [x] Path and temporary-directory safety added: storage-path escape rejection and temp roots inside the source tree.
- [x] Stored-media processing can resolve media files through the configured local storage root.
- [x] Frontend API client added with typed contracts, retryable errors, upload progress, auth-token boundary, and local proxy support (`/api` -> `http://localhost:8000`).
- [x] `NewTranscriptionPage` now uploads through `initiate` -> signed PUT -> completion, derives lecture/job status from backend data, and shows progress while submitting.
- [x] Development-only local bearer-token input added; mobile/prototype production builds do not expose token entry, and the token remains React state rather than being persisted.
- [x] Visible upload progress and backend status messages added; retry feedback remains through the existing `ApiError` handling.

## Step 4 verification
- Ruff: passed (`ruff check backend`; 0 findings).
- Backend tests: passed (`pytest` in `backend/`, 21 tests).
  - `tests/test_media.py`: 9 tests passed (silence/bypass, stereo-to-mono normalization, runtime checks, VAD offsets, IEEE-float parsing, storage-path escape, stored media, missing audio).
  - Existing adapter/auth/config/health/upload tests passed; 3 FastAPI/httpx deprecation warnings remain non-blocking.
- Frontend lint: passed (`npm run lint`; 0 warnings/errors after fixing an unused limit destructuring in `api.ts`).
- Frontend typecheck/build: passed (`npm run build`, `tsc -b && vite build`).
- Frontend tests: mixed (`npm test -- --run`; 6 passed, 2 failed).
  - Failing tests remain the same pre-existing `src/App.test.tsx` failures: protected routes render the sign-in page before authenticated LectureFlow content.
  - Recording flows and chat flows passed.
- FFmpeg: available and used by media tests (`8.1.2-full_build-www.gyan.dev` build).
- Backend local smoke: FastAPI `TestClient` returned HTTP 200 from `/api/health` (`uvicorn` is not available as an installed CLI in this tool environment).
- Frontend local smoke: Vite development server returned HTTP 200 at `http://localhost:5173/`; production build already passed.
- Authenticated upload E2E remains owner-gated: local Firebase ID-token verification requires an available Firebase Admin setup/public user setup, and hosted provider work is not yet provisioned.
- Manual localhost operator check can still use the Vite `/api` proxy to `http://localhost:8000` once a backend server process is available.
- Cloud credentials, billing/region, worker service account, hosted provider keys, demo lecture consent, dataset access, FFmpeg installation, and owner-set tolerances/budget.

## Merge repair (before any further work after the `iteration_lim` merge)
- Problem: `278f551` and merge commit `a8df037` committed unresolved conflict markers in `backend/app/main.py`, `backend/app/config.py`, `backend/requirements.txt` and `frontend/src/services/api.ts`. `main.py` raised `SyntaxError` at import (backend would not start), `config.py` held two competing `Settings` classes, `requirements.txt` could not be installed, `api.ts` did not typecheck, and `RecordingProvider.tsx` ended with a stray `ss`.
- Fix (`a467340`): union merge for `main.py`/`requirements.txt`/`api.ts` (Step 1 foundation + `iteration_lim` transcription flow both kept); field-level merge for `config.py` into a single pydantic `Settings` with `max_upload_mb=512` (owner value) and `ENHANCE_AUDIO`/`TRANSCRIBE_WORKERS` preserved as env aliases; stray fragment removed; required `ChatSession.storagePath` initialized; `App.test.tsx` seeded with the demo session and updated to the current HomePage/NewTranscriptionPage UI.
- Follow-up (`585ced7`): `ruff check` and `ruff format` brought to pass — this is exactly what `ci.yml` runs; 42 auto-fixes plus 17 manual (FastAPI `Depends`/`File` noqa, intentional catch-alls, context managers in `evaluate.py`).
- Verification: `python -m compileall` pass; `ruff check backend` + `ruff format --check backend` pass; `pytest` 40 passed; `npm run lint` and `npm run build` pass; `npm test -- --run` 9/9 (the 2 previously failing `src/App.test.tsx` tests were stale against the current UI).

## Upload -> DSP -> ASR (partial Step 8, owner-requested)
- Step 5 note: the ASR adapter code (`asr.py`, `dsp.py`, `jobs.py`) arrived with `278f551` and was undocumented/unverified; it is now reachable from the upload path.
- Implemented in `ce083c6`:
  - [x] `backend/app/worker.py`: claim queued job with lease + heartbeat -> validate -> `LocalMediaService` (Arm A + DSP stages) -> `transcribe_file(enhance=False)` -> `completed`/`failed`.
  - [x] FastAPI lifespan start/stop behind `WORKER_ENABLED` (default on); `backend/tests/conftest.py` forces it off so `with TestClient(app)` stays deterministic.
  - [x] Job stage, DSP configuration, per-stage runtimes, diagnostics and ASR provider/model/segment count recorded in `JobDocument.timings`; lecture state moved to `completed`/`failed` so `GET /api/lectures/{id}` reflects the result.
  - [x] Transcript persisted to `users/{owner}/{lecture}/transcript.json` through the storage adapter (readable through the existing signed download route).
  - [x] Single DSP switch: `enhance_default` now defaults to `false`, so `dsp.py` is evaluation/`app.evaluate` only and `media.py` is the pipeline DSP.
  - [ ] Not wired: chunks, embeddings, notes, exports, deletion (Steps 6, 7 and the rest of Step 8).

## Upload -> DSP -> ASR verification
- Ruff: passed (`ruff check backend`, `ruff format --check backend`).
- Backend tests: passed (`pytest` in `backend/`, 46 tests; 9.6 s on an idle machine).
- New coverage (`tests/test_worker.py`, 6 tests): one-DSP-pass assertions with `DSP_ENABLED=false` (Arm A baseline) and `true` (filtered file), DSP failure -> failed job + failed lecture, empty-queue return, lifespan flag gate, and an end-to-end API upload whose job must reach the lifespan worker's repository.
- Frontend re-verified in this pass: `npm run lint` 0 problems, `npm run build` passed, `npm test -- --run` 9 passed.
- Not run / not claimed: real Whisper model download (`MODEL_CACHE_DIR` download is owner-gated), Firestore emulator and Firestore worker scan (the in-memory path is what is verified), container run, Firebase emulator rules (Java/`firebase-tools` unavailable), Step 5A harness (not started).

## Phase 3: Output Quality (in progress)

- RAG pipeline (FAISS vector store, OpenAI answer generator) integrated and unit‑tested.

- Evaluation harness (Step 5A) dataset preparation: E2, E3, and E4 datasets are ready for preprocessing; M3AV download is pending.
- Metric scripts (`eval/metrics.py`, `eval/run.py`, etc.) are in place, awaiting execution with real provider keys.
- Focus tasks: run Tier 2 evaluation, generate results, refine retrieval, answer generation, and notes based on metric outcomes.

## Phase 4: Optimization & Release (pending)

- Profile pipeline stages (DSP, ASR, embedding, retrieval, answer generation) and implement caching.
- Implement resumable uploads, cancellation, and robust error handling for large files.
- Finalize deletion workflow across storage, jobs, chunks/vectors, notes, and Q&A history.
- Conduct security‑rule audits, secret scans, and full CI verification before production deployment.
