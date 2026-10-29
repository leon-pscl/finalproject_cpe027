# Development Plan (Build Steps on `iteration_pascual`)

Maps `docs/instructions.md` (Rev 2.3) to the v3 Build Steps. Branch is `iteration_pascual` only; Gates A/B/C control promotion.

## Cross-cutting architecture
- Identity: Firebase Auth; API verifies ID tokens with Firebase Admin SDK, revocation checked.
- Data: Firestore Native with owner isolation; Admin SDK usage only in worker/API with explicit ownership.
- Media: Cloud Storage private bucket, owner-scoped paths; signed uploads, server-verified objects.
- Queue: Firestore transactional lease queue; deterministic job ID `{lectureId}_{version}`.
- Processing modes: `PROCESSING_MODE=mock|real`, `ENV=dev|staging|production`; reject mock mode in production.
- Adapters: `MediaService`, `AudioProcessor`, `Transcriber`, `Chunker`, `Embedder`, `Retriever`, `AnswerGenerator`, `NotesGenerator` exposed by `Mock*` and safe `Real*` (not configured in safe local mode).
- Vector search: Firestore vector fields; server-side only; owner/lecture/version filter before NN.

## Build Steps

### Step 1: Audit, docs, foundation, CI (this pass)
- Audit done (`docs/repo-audit.md`).
- Foundation modules and adapter interfaces.
- Firebase rules/indexes/emulator config + `.env.example`.
- CI with pinned versions; no model/dataset downloads.

### Step 2: API, upload, job queue
- Endpoints, signatures, verification, quotas, stable errors.
- Transactional job claim, lease, heartbeat, bounded attempts, idempotency, stages.

### Step 3: Frontend upload workflow
- File upload path, validation, progress, polling; required UI states.
- API client behind existing service interface; minimal UI edits.

### Step 4: Media and DSP engine
- Safe FFmpeg extraction, normalized Arm A baseline, bypassable DSP chain with configs, diagnostics.

### Step 5: ASR adapter
- Hosted Whisper-class default + optional faster-whisper; chunking + offset map; anti-loop/hallucination; budgets/timeouts.

### Step 5A: DSP evaluation harness
- `eval/`, `docs/evaluation-protocol.md`, manifests, frozen sets/key-term lists, runner Arms A/B/C, metrics, binning, statistics, regeneration command, `docs/dsp-evaluation-results.md` (scaffolded).

### Step 6: Chunking, embeddings, vector index
- Segment-aware overlapping chunks; embedder; Firestore composite vector index; server-side filtered queries.

### Step 7: RAG answering and notes
- Evidence-only answering with source ID/timestamp validation; prompt-injection resistance; notes with failure tolerance; version activation safety.

### Step 8: Worker wiring, exports, deletion
- Full idempotent pipeline; exports; seeking; deletion across all data.

### Step 9: Verification report (Gate A)
- Full check suite + one end-to-end recording; `docs/pipeline-report.md`; stop and report.

## Gates
- Gate A: all mandatory checks + one approved real run on branch; owner decides.
- Gate B: integration with teammate UI in `iteration1-merged`; preserve teammate work; re-run checks.
- Gate C: promotion to `main` with CI, mock rejection in prod, secret scan; deployment needs owner approval.

## Evaluation (after Gate A)
- Public datasets E1-E4 only; manifests only. Paired design and decision rule. DSP comparison run earlier in Step 5A; treat Gate A comparison as broader integration.

## Safe local mode (first passes)
- No cloud credentials assumed. Interfaces + mocks + emulator tests + local FFmpeg only. Hosted runs only in a separately authorized workflow.

---

**Checkpoint:** See `docs/checkpoint.md` for a summary of the RAG pipeline implementation and next steps.
