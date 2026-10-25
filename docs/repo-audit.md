# Repository Audit (Build Step 1)

## Scope inspected
- `frontend/src/` (entry, routing, `App.tsx`, `auth/`, `pages/`, `services/mock/`, `recording/`)
- `backend/` (`app/main.py`, tests, requirements, Docker)
- `docs/instructions.md` (Rev 2.3), `docs/agent_tasks_v3_pascual_branch.md`, `docs/step5A_dsp_evaluation_insert.md`

## What is real vs mocked

### Frontend (`frontend/`)
- Build/runtime: React 19, Vite 6, TypeScript, Tailwind 3.4, React Router 6. UI is a single large `App.tsx` containing most pages and processing simulation.
- Auth: `auth/AuthProvider.tsx` stores a synthetic session in `localStorage`; no token verification, no Firebase. `useAuth`, `ProtectedRoute`.
- Service layer: only `services/mock/index.ts`. It synthesizes transcript/notes for any uploaded file via `buildLectureProject` / `generateTranscript` / `generateNotes`; no network calls. Upload handling and duration estimation are client-side approximations.
- Recording: `recording/` captures audio/video from the microphone with MediaRecorder and persists blobs in IndexedDB (`audioStore.ts`). Optional local feature; not an upload-to-backend flow.
- DSP UI: `services/mock` exposes DSP preset controls and `validateAudio` supporting `.wav/.mp3/.m4a`; mappings are cosmetic for now.
- Tests: frontend `vitest` exists (`App.test.tsx`, `recording/*.test.tsx`); verifies mocked UI only.

### Backend (`backend/`)
- FastAPI scaffold with a single `GET /api/health` (`app/main.py`). No auth, storage, Firestore, job queue, or processing.
- `tests/test_health.py` only.
- `requirements.txt`: `fastapi`, `uvicorn`. `requirements-dev.txt` present (not yet inspected for tool versions; update in foundation step).
- Docker files present (`backend/Dockerfile`, root `Dockerfile`, `compose.yaml`, `nginx.conf`).

### Infrastructure
- No `firebase/`, no `.env.example`, no CI workflow, no adapter interfaces, no docs beyond instructions and the two task files.

## Current state classification
- No real processing pipeline exists; all lecture output is fixture/synthetic.
- Processing simulation is mock-only and must not be presented as processed content for arbitrary uploads.
- No persistent identity, data, or storage; all data is browser-local and volatile.

## Test status (pre-change)
- Backend: 1 health test.
- Frontend: lint/build/test available; no backend integration or security coverage.
- No Security Rules, emulator, or cross-user isolation tests.

## Dependencies not yet available (safe local mode)
- Firebase Admin SDK, Cloud Run worker, hosted ASR/embedding/LLM credentials, public datasets, FFmpeg runtime, `firebase-tools`/Java are not assumed. Checks needing them remain documented as blocked.

## Guardrails for foundation work
- Extend `backend/app`; do not rewrite `App.tsx` wholesale; keep edits to existing UI minimal.
- Preserve user's unrelated working changes in the repository.
- Separate labeled commit for Build Step 1.