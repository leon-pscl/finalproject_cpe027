# Phase Status

## Current position
- Branch: `iteration_pascual` at `fc8a926` (pushed, includes owner-approved retained stray package-lock commit).
- Promotion path: `iteration_pascual` -> `iteration1-merged` -> `main`.
- Operating mode: safe local (no cloud credentials assumed; hosted runs separately authorized).
- Active build step: Step 2 in progress (upload/job-queue layer implemented locally; not yet owner-tested or merged).

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

## Remaining blockers before later gates
- Cloud credentials, billing/region, worker service account, hosted provider keys, demo lecture consent, dataset access, FFmpeg installation, and owner-set tolerances/budget.