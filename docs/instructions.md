# Coding-Agent Instructions: Lecture-Video Assistant

## Purpose

Build a secure web application that turns an authorized lecture-video upload into a timestamped transcript, structured study notes, and lecture-grounded question answering with playable source references. Implement the project iteratively, following the four phases below; do not attempt to build the entire system in one pass.

This brief follows the confirmed development sequence:

| Phase | Primary focus | Required outcome |
|---|---|---|
| 1 | Basic UI, input/output, Supabase, Vercel, deployment | A deployed end-to-end application using clearly labeled processing fixtures |
| 2 | DSP, pretrained ASR, embeddings, and RAG | The same workflow operates on real lecture content |
| 3 | Improve outputs | Measurable improvements to transcripts, notes, answers, and timestamp references |
| 4 | Further optimizations and final changes | A tested, documented, reproducible release candidate |

**Status of decisions:** The four-phase sequence is confirmed. The architecture, defaults, tests, and acceptance gates below are proposed implementation instructions, not previously approved research thresholds or claims of achieved performance. Preserve compatible existing project decisions; record any necessary deviation before implementation.

## Agent Operating Rules

1. Inspect the repository, existing requirements, environment templates, and deployment configuration before changing files. Extend working code rather than replacing it unnecessarily.
2. Create `docs/development-plan.md`, mapping this brief to repository tasks, and `docs/phase-status.md`, recording the current phase, completed work, evidence, and blockers.
3. Work on one phase at a time. Use small feature branches and pull requests; keep the deployed baseline usable.
4. Complete that phase's required tasks and acceptance checks before proposing progression. Stop for owner approval at each phase boundary unless continuous progression was explicitly authorized.
5. Do not silently substitute mocks for real processing, invent benchmark results, or report unexecuted tests as passed.
6. Do not introduce model training, a second vector database, agentic orchestration, or major infrastructure unless the existing implementation demonstrates a specific need.
7. If credentials, deployment permissions, approved media, or inference hardware are unavailable, complete safe local work and document the blocked external check. Do not claim deployment or acceptance is complete.
8. Do not delete existing data, rotate credentials, change billing, provision paid resources, or run destructive migrations without approval.
9. At every handoff, report implemented changes, affected files, executed checks, deployment status, limitations, and the next permitted task.

## Product Boundaries

### Required workflow

1. Sign in and view a private lecture library.
2. Upload a supported lecture recording and enter its title.
3. See upload progress and durable processing status.
4. Open a workspace containing the original video, timestamped transcript, study notes, and question-answer interface.
5. Ask a question about that lecture and receive an evidence-backed answer or an explicit insufficient-evidence response.
6. Select a source reference to seek the original recording to the relevant segment.
7. Export the transcript as TXT/VTT and notes as Markdown; delete a lecture and its derived data.

### Initial exclusions

- Live transcription, real-time meetings, external URL downloading, and unrestricted web retrieval.
- Training or fine-tuning ASR, embedding, or language models.
- Speaker diarization, slide OCR, visual question answering, and automatic grading.
- Cross-lecture search, shared classrooms, billing, and institutional administration.
- Claims of perfect transcription, guaranteed factual correctness, or understanding of information visible only on slides.

Treat the recording's audio transcript as the initial knowledge source. State that slide-only equations, diagrams, and text are outside this version's evidence coverage.

## Architecture and Contracts

### Proposed stack

| Layer | Implementation instruction |
|---|---|
| Web | Next.js, TypeScript, Tailwind CSS; deploy the frontend to Vercel |
| Identity and data | Supabase Auth, PostgreSQL, private Storage, and pgvector |
| API | Python FastAPI with Pydantic request/response validation |
| Processing | A separately deployed Python worker/container; FFmpeg, NumPy/SciPy, `faster-whisper`, and an embedding adapter |
| Language generation | A configurable pretrained model provider behind one server-side adapter |
| Quality | GitHub Actions; Ruff, Pytest, frontend lint/type checks, and browser workflow tests |

Use compatible existing dependencies where possible. Pin package versions, model identifiers/revisions, and container dependencies after compatibility testing. The choices above are implementation defaults, not performance comparisons or claims about current hosting quotas.

**Deployment boundary:** Deploy the web frontend separately from long-running media/model processing. The API must create durable jobs and return promptly; do not make a page request wait for transcription. Inspect actual account limits during setup and record the selected worker host, hardware, storage, and upload constraints in `docs/deployment.md`.

### Processing flow

```text
Browser -> Authentication -> Authorized private upload -> Lecture/job record
                                                       |
                                                       v
                                      Persistent worker claims queued job
                                                       |
                         Media validation -> Audio extraction -> DSP
                                                       |
                              ASR -> Timed segments -> Timed chunks
                                                       |
                                      Embeddings -> Private vector index
                                                       |
                                      Source-linked notes -> Ready state

Question -> Ownership check -> Lecture/version-scoped retrieval
         -> Evidence-constrained generation -> Citation validation
         -> Answer + server-resolved timestamps -> Video seek
```

Use a PostgreSQL-backed job queue initially. Implement atomic job claiming, an expiring lease/heartbeat, bounded retries, and idempotent processing. A second queue service is optional only after a demonstrated need.

### Suggested repository layout

```text
apps/web/                   # UI, authentication, player, API client
services/api/               # FastAPI endpoints and authorization
services/worker/            # Durable job runner and pipeline
packages/contracts/         # Shared schemas / generated TypeScript types
supabase/migrations/        # Tables, indexes, RLS, storage policies
tests/                      # Integration and end-to-end checks
 docs/                      # Architecture, decisions, phase reports
```

Prefer a simpler existing layout over a disruptive restructuring.

### Data requirements

Create versioned migrations for these entities:

| Entity | Minimum information |
|---|---|
| `lectures` | ID, owner ID, title, storage path, original duration, media metadata, state, active processing version, deletion marker |
| `processing_jobs` | ID, lecture ID, owner ID, processing version, stage, state, attempts, lease/heartbeat, safe error code, timings |
| `transcript_segments` | ID, lecture ID, processing version, segment order, original-timeline start/end seconds, text, diagnostic flags |
| `transcript_chunks` | ID, lecture ID, processing version, constituent segment IDs, text, embedding, embedding model/revision |
| `study_notes` | Lecture/version, structured sections, supporting segment IDs, model/prompt version |
| `qa_turns` | Owner/lecture/version, question, answer status, answer blocks, supporting segment IDs, model configuration |

Use one embedding configuration and vector dimension per active index. Reject incompatible query embeddings; change the index through an explicit migration/reindexing workflow rather than mixing dimensions or model spaces.

### Stable interfaces

Define typed adapters before implementing models:

```text
MediaService.validate_and_extract(lecture_id, processing_version)
AudioProcessor.process(audio_asset, config)
Transcriber.transcribe(audio_asset, config)
Chunker.chunk(timed_segments, config)
Embedder.embed(texts, config)
Retriever.search(owner_id, lecture_id, processing_version, question)
AnswerGenerator.answer(question, authorized_evidence, config)
NotesGenerator.generate(authorized_timed_chunks, config)
```

Expose the same interface from `Mock*` and `Real*` adapters. Select implementations through validated configuration such as `PROCESSING_MODE=mock|real`; never put model-selection logic inside UI components.

Define the answer response as a versioned contract. Each substantive answer block must reference one or more server-issued source IDs; the server resolves those IDs into segment text and timestamps. Include `answer_status` (`answered`, `insufficient_evidence`, or `error`), lecture/version identifiers, and an explicit processing mode. Do not accept model-invented URLs, segment IDs, or timestamps as evidence.

### API behavior

Implement and document equivalents of these endpoints:

| Endpoint | Required behavior |
|---|---|
| `POST /lectures/uploads` | Authenticate; create pending lecture and an authorized, scoped upload destination |
| `POST /lectures/{id}/upload-complete` | Verify ownership and actual stored media; finalize upload and enqueue one idempotent job |
| `GET /lectures` | Return only the authenticated owner's lectures |
| `GET /lectures/{id}` | Return authorized metadata and processing status |
| `POST /lectures/{id}/retry` | Retry eligible failures without creating duplicate active jobs |
| `GET /lectures/{id}/transcript` | Return the authorized active transcript and processing version |
| `GET /lectures/{id}/notes` | Return source-linked notes when available |
| `POST /lectures/{id}/questions` | Validate ownership/readiness; retrieve and answer within the active lecture/version |
| `GET /lectures/{id}/exports/{format}` | Export only owner-authorized transcript or notes |
| `DELETE /lectures/{id}` | Mark inaccessible, stop work safely, and schedule complete deletion |
| `GET /health` | Report service health without credentials or private content |

Use opaque IDs, request validation, bounded pagination, and stable error codes. Derive the owner from verified authentication, not a client-supplied `owner_id`. Use 202 for accepted asynchronous processing, and document authorization/error responses consistently.

## Phase 1: Foundation

**Goal:** Deploy a usable application shell with real authentication, storage, persistence, input/output, and clearly labeled processing fixtures. Do not load inference models yet.

### Required tasks

- [ ] Inspect the repository and create the phase task map and architecture decision log.
- [ ] Initialize the web app, API, lightweight worker skeleton, lockfiles, containers, and `.env.example` without real secrets.
- [ ] Create Supabase migrations, private buckets, row-level security policies, and owner-scoped storage policies.
- [ ] Implement sign-in, sign-out, protected routes, session expiry handling, and private lecture listing.
- [ ] Build upload, lecture workspace, original-video player, transcript, notes, chat, export, and delete screens.
- [ ] Upload directly to private storage using an authorized upload flow; validate file type, configured size, and stored-object metadata server-side before processing.
- [ ] Implement durable job creation/status and visible stages: `queued`, `validating`, `extracting`, `preprocessing`, `transcribing`, `indexing`, `generating_notes`, and `completed`; distinguish `failed` and `cancelled` terminal states.
- [ ] Use a checked-in, authorized demonstration recording with aligned fixture transcript/notes/answers. Label every fixture-derived result **Demo output — not processed from this upload**.
- [ ] For arbitrary uploaded recordings, show the upload/player/status workflow, but do not present the demonstration transcript as their actual content.
- [ ] Wire source clicks to video seeking and implement export formats using the demonstration fixture.
- [ ] Implement empty, loading, retryable-error, unsupported-file, expired-session, and no-evidence states.
- [ ] Add responsive layout, visible focus, keyboard-operable controls, descriptive labels, and accessible status announcements from the beginning.
- [ ] Configure staging deployment, health checks, environment separation, and CI quality checks.

Mock mode may run only in development or a visibly labeled preview. Reject mock mode for the final production release. Require authentication and isolation even for previews accepting real uploads.

### Acceptance gate

- [ ] A fresh checkout builds using documented commands and environment variables.
- [ ] Staging supports sign-in, upload, persistence across refresh, lecture opening, playback, fixture viewing, export, and deletion.
- [ ] Users A and B cannot list, read, download, export, or delete each other's lecture data; direct API and storage access are tested.
- [ ] Invalid uploads and failed jobs produce actionable UI states without leaking internal exception details.
- [ ] CI passes and no model inference is necessary for this phase's smoke test.
- [ ] `docs/phase-1-report.md` records the deployed URLs, executed checks, fixture boundaries, and unresolved deployment blockers.

**Do not start Phase 2 until the deployed shell and contracts are accepted.**

## Phase 2: DSP and Models

**Goal:** Replace the fixture adapters with a real, persistent audio-to-transcript-to-RAG pipeline without redesigning the UI.

Pretrained Whisper models support an inference-first prototype rather than training a recognizer from scratch. [cite:25] [R1](#r1)

### Media and DSP tasks

- [ ] Probe actual media streams, duration, codec, and decode success; reject malformed files and recordings without usable audio.
- [ ] Extract audio with FFmpeg using safe argument lists, execution timeouts, resource limits, and temporary-directory cleanup.
- [ ] Create a mono, 16 kHz ASR working copy; retain the original video and a normalized, non-enhanced comparison baseline.
- [ ] Add configurable DSP stages: level normalization with clipping protection, optional conservative noise reduction, and optional filtering when justified by the signal.
- [ ] Keep enhancement bypassable. Do not enable an aggressive filter merely because the audio sounds cleaner.
- [ ] Record audio duration, sample rate, channel conversion, clipping/silence diagnostics, processing parameters, and stage runtimes.
- [ ] Preserve original-video timing. If VAD, trimming, or chunking removes time, maintain and test an explicit offset mapping before persisting segments.
- [ ] Handle silent audio, stereo input, low-volume speech, noisy speech, and chunk-boundary speech without inventing transcript content.

Enhancement artifacts can worsen recognition; compare the baseline and enhanced branches before choosing the default. [cite:11] [R2](#r2)

### ASR and retrieval tasks

- [ ] Integrate `faster-whisper` behind `Transcriber`; choose a multilingual checkpoint compatible with the actual hardware and intended lecture languages.
- [ ] Record model/revision, device, compute type, decoding settings, detected/requested language, and audio/DSP configuration.
- [ ] Persist ordered segment text and original-timeline start/end times; retain diagnostic fields without presenting them as calibrated accuracy probabilities.
- [ ] Build overlapping, segment-aware transcript chunks; preserve segment IDs and time ranges through embedding and retrieval.
- [ ] Use a pinned pretrained embedding adapter and Supabase pgvector; keep chunk size, overlap, retrieval count, and context budget configurable.
- [ ] Constrain retrieval by authenticated owner, selected lecture, and active processing version before selecting nearest matches.
- [ ] Integrate a pretrained language-model adapter; secrets and provider requests remain server-side.
- [ ] Generate concise answers only from authorized retrieved evidence. If evidence is absent or insufficient, return an explicit limitation rather than a plausible guess.
- [ ] Validate every output source ID against the retrieved evidence and resolve timestamps server-side. Invalid references cause a safe retry or controlled failure.
- [ ] Produce basic structured notes from timed chunks, retaining source references through any hierarchical summarization.
- [ ] Keep answers and transcript viewing usable if note generation alone fails; represent partial completion and offer an appropriate retry.
- [ ] Prevent stale versions from replacing newer results; mark a version active only after its required transcript/index stages pass validation.

### Acceptance gate

- [ ] An approved real recording completes upload, DSP, ASR, indexing, notes, and grounded Q&A on the deployed worker.
- [ ] The worker can restart and recover an interrupted job through lease expiry without duplicate active results.
- [ ] Repeating the same request does not duplicate segments, embeddings, or active jobs.
- [ ] All persisted segments have ordered, valid bounds within the original duration; all displayed references resolve to authorized segments.
- [ ] A no-audio/silent recording and a provider timeout fail safely; no fixture is silently returned.
- [ ] A cross-user retrieval attempt returns no unauthorized content, including when the worker uses privileged database credentials.
- [ ] A small, authorized real evaluation set and its human reference annotations are recorded as the baseline, with actual stage timings and observed errors.
- [ ] `docs/phase-2-report.md` identifies real versus unexecuted checks, deployment configuration, supported languages, and remaining limitations.

## Phase 3: Output Quality

**Goal:** Improve the quality of information delivered to students, using measured comparisons rather than UI polish alone.

Evaluate retrieval and answer quality separately instead of treating a fluent final response as sufficient evidence of correctness. [cite:26] [R3](#r3)

### Required tasks

- [ ] Freeze a development evaluation set and a separate held-out set from authorized recordings. Store media provenance, annotation procedure, questions, answerability labels, and reference segments.
- [ ] Include clean/noisy speech, pauses, technical vocabulary, long-form content, and intended languages when representative recordings are available; report missing coverage.
- [ ] Compare normalized-only audio against the DSP-enhanced version using identical ASR settings. Keep a bypass when enhancement regresses the evaluated conditions.
- [ ] Improve decoding, chunk boundaries, repetition handling, and technical-term hints without replacing uncertain words with invented lecture content.
- [ ] Tune chunk size, overlap, retrieval count, context ordering, and the insufficient-evidence decision on the development set only.
- [ ] Add reranking or hybrid retrieval only if a documented failure case and measured benefit justify the extra dependency.
- [ ] Improve notes with topic headings, key points, source-linked definitions, and readable organization; do not invent slide-only material or unspoken explanations.
- [ ] Support questions requiring multiple segments when the retrieved evidence is sufficient. Preserve all relevant references rather than attaching one arbitrary timestamp.
- [ ] Handle follow-up questions by using authorized same-lecture history to clarify the retrieval query; history is not independent evidence.
- [ ] Add concise uncertainty/coverage notices for unclear transcription or missing evidence; do not display an uncalibrated confidence percentage.
- [ ] Test source-click seeking, VTT alignment, long transcript rendering, empty retrieval, and evidence distributed across chunk boundaries.

Citation presence is not evidence support; evaluate citation correctness and coverage separately. [cite:24] [R4](#r4)

### Evaluation contract

Create `docs/evaluation-protocol.md` and machine-readable evaluation outputs. Record the definition and denominator of each metric.

| Area | Required measurement | Release decision rule |
|---|---|---|
| Transcription | WER using a fixed documented text-normalization policy; report per language/condition | Choose DSP/model changes using measured results, not listening impressions alone |
| Retrieval | Recall@k over annotated supporting segment IDs | Compare with the frozen Phase 2 configuration |
| Answer quality | Human-reviewed correctness and unsupported-claim rate | Reject changes that trade apparent fluency for additional unsupported claims |
| Citations | Valid-ID rate, supporting-reference precision, claim coverage, and observed seek offset | Require structurally valid references; inspect semantic support manually |
| Abstention | Correct abstention on unanswerable questions and false refusal on answerable questions | Report both; avoid improving one by refusing every question |
| Notes | Human review of factual support, topic coverage, and readability | Every substantive section must retain resolvable evidence |
| Efficiency | Stage runtimes, real-time factor, memory observations, and request latency | Report hardware, sample count, warm/cold conditions, and failure rate |

Use real, human-checked evaluation annotations. Artificial fixtures are permitted for unit tests only and must not be reported as real performance evidence. An optional LLM evaluator supplements, rather than replaces, human review of this small prototype evaluation set.

Set numerical quality and latency targets with the project owner after the Phase 2 baseline; freeze them before final evaluation. Until approved, label results as measured comparisons rather than a validated pass against invented thresholds. For small samples, disclose counts and avoid unsupported generalization.

### Acceptance gate

- [ ] A reproducible comparison shows what changed from Phase 2 and whether each chosen change improved its intended metric.
- [ ] The held-out set was not used to repeatedly tune configuration; any contamination is disclosed and evaluation is refreshed where feasible.
- [ ] All answer references resolve; malformed references and unsupported citation attempts are rejected by contract tests.
- [ ] Human review covers answer support, note support, answerable/unanswerable behavior, and playback alignment.
- [ ] Remaining failures are categorized and visible in `docs/phase-3-report.md`; improvements and regressions are both reported.

## Phase 4: Optimization and Release

**Goal:** Stabilize the accepted system, optimize demonstrated bottlenecks, and prepare an honest, reproducible handoff.

### Required tasks

- [ ] Profile before optimizing; separate extraction, DSP, ASR, embedding, retrieval, and generation costs.
- [ ] Reuse loaded model instances within the worker's resource budget; tune batching/concurrency only after memory and correctness checks.
- [ ] Cache transcripts, embeddings, and notes by content and processing configuration within an owner's authorized scope. Never expose cross-user cache hits or reuse stale-version artifacts.
- [ ] Improve large-file upload reliability, cancellation, bounded retries, and readable stage progress; do not present guessed percentages as measured completion.
- [ ] Paginate or virtualize long transcripts and large lecture lists where profiling demonstrates a need.
- [ ] Add bounded request sizes, upload quotas, per-user rate controls, provider timeouts, and output/token budgets.
- [ ] Finish keyboard/mobile testing, focus behavior, loading/error recovery, and readable feedback.
- [ ] Review migrations, indexes, orphan cleanup, dependency risks, and secret handling.
- [ ] Implement and test lecture/account data deletion across storage, jobs, segments, chunks/vectors, notes, and Q&A history. Deletion must stop new work from recreating removed artifacts.
- [ ] Keep signed playback URLs short-lived and document any expiry window; do not promise immediate revocation of already issued URLs unless implemented and verified.
- [ ] Re-run functional, isolation, security, quality, and deployment checks against the release candidate.
- [ ] Publish setup, architecture, environment, model/license, deployment, evaluation, limitations, rollback, and demo instructions.

### Acceptance gate

- [ ] A clean installation and migration works using the documented configuration.
- [ ] The final deployment runs real processing; production rejects mock mode and exposes no privileged secrets.
- [ ] Upload-to-answer, playback references, exports, retry, deletion, and worker restart recovery pass on the target deployment.
- [ ] All mandatory automated checks pass; external checks not executed are explicitly listed rather than marked passed.
- [ ] Before/after quality and optimization results are reproducible with model/configuration versions and observed resource constraints.
- [ ] The release has a tagged commit, deployment record, rollback procedure, and owner-approved limitations.

## Security Throughout Development

RAG introduces privacy and adversarial risks; treat lecture text and retrieved passages as untrusted data, not executable instructions. [cite:15] [R5](#r5)

- Enforce owner isolation on lecture metadata, storage, transcripts, embeddings, retrieval queries, exports, playback, and Q&A history from Phase 1 onward.
- Enable RLS and test it directly. Prefer security-invoker retrieval functions; audit any privileged function or service-role path for explicit ownership enforcement.
- Verify JWTs at the API; never authorize from client-controlled IDs or an unverified decoded token.
- Keep Supabase service-role and model-provider keys exclusively in backend/worker environments. Never put them in browser-public variables or logs.
- Authorize before issuing short-lived media URLs; keep buckets private.
- Treat uploaded filenames and transcript text as untrusted. Avoid shell interpolation, executable markup, unsafe rendering, and prompt-controlled tool access.
- Explicitly instruct generation to ignore instructions embedded in lecture evidence; back this with injection tests and authorization outside the model prompt.
- Never give the model unrestricted database, filesystem, networking, or administrative tools.
- Use approved recordings only; describe external provider processing and obtain the necessary permission before sending lecture content to that provider.
- Log request/job IDs, stages, safe error codes, and timings. Avoid logging full lectures, questions, tokens, signed URLs, or private transcript text by default.
- Do not claim ISO certification, accessibility conformance, or production-grade security solely because checklists or linters pass.

## CI/CD and Evidence

Create actual repository scripts matching the following checks; document equivalent commands if the existing project uses a different package manager.

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web typecheck
pnpm --dir apps/web test
pnpm --dir apps/web build
ruff check services
ruff format --check services
pytest
```

Require these checks on pull requests. Use PEP 8-oriented Python conventions with a documented Ruff rule set; lint success is not a guarantee of complete style or software-quality compliance. Pin supported Python/Node versions and commit lockfiles.

- Run deterministic unit/contract tests with clearly identified fixtures; do not download large models on every pull request.
- Run database/RLS integration checks against an isolated test instance, never the live project database.
- Run browser smoke checks for authentication, upload, status, player seek, Q&A states, exports, and deletion.
- Place real-model/deployed-worker smoke tests in a separately authorized workflow with secrets and an approved sample recording.
- Report test coverage for critical modules and add regression tests for each discovered privacy, timestamp, retrieval, or job-recovery defect.
- Deploy to staging before promoting an approved release; keep staging storage and secrets separate from production.
- Review migration compatibility and backup/rollback needs before promotion. Never automate destructive migration approval.

## Handoff and Starting Instruction

Every phase report must contain: scope completed, changed modules, exact executed test commands and results, deployment verification, evidence files, known limitations, unresolved approvals, and the proposed next step. Include a short demo path that another team member can reproduce.

**Start now:** Inspect the repository and produce the Phase 1 task map. Implement only Phase 1 until its acceptance gate has been reviewed. Preserve the contracts so Phase 2 can replace fixtures without rewriting the user interface.

## References

These sources inform selected ASR, DSP, RAG evaluation, citation, and security decisions. The stack and phase gates are project-specific recommendations, not requirements established by these papers. All references below are IEEE or open-access academic works published within 2021–2026; preprints are labeled.

<a id="r1"></a>
**R1.** A. Radford et al., “Robust Speech Recognition via Large-Scale Weak Supervision,” in *Proceedings of the 40th International Conference on Machine Learning*, PMLR, vol. 202, pp. 28492–28518, 2023. Open access: https://proceedings.mlr.press/v202/radford23a.html. [cite:25]

<a id="r2"></a>
**R2.** T. Ochiai et al., “Rethinking Processing Distortions: Disentangling the Impact of Speech Enhancement Errors on Speech Recognition Performance,” arXiv:2404.14860, 2024, open-access preprint. DOI: https://doi.org/10.48550/arXiv.2404.14860. [cite:11]

<a id="r3"></a>
**R3.** S. Es, J. James, L. Espinosa Anke, and S. Schockaert, “RAGAs: Automated Evaluation of Retrieval Augmented Generation,” in *Proceedings of EACL: System Demonstrations*, pp. 150–158, 2024. DOI: https://doi.org/10.18653/v1/2024.eacl-demo.16. Open access: https://aclanthology.org/2024.eacl-demo.16/. [cite:26]

<a id="r4"></a>
**R4.** T. Gao, H. Yen, J. Yu, and D. Chen, “Enabling Large Language Models to Generate Text with Citations,” in *Proceedings of EMNLP*, pp. 6465–6488, 2023. DOI: https://doi.org/10.18653/v1/2023.emnlp-main.398. Open access: https://aclanthology.org/2023.emnlp-main.398/. [cite:24]

<a id="r5"></a>
**R5.** B. Ni et al., “Towards Trustworthy Retrieval Augmented Generation for Large Language Models: A Survey,” arXiv:2502.06872, 2025, open-access preprint. DOI: https://doi.org/10.48550/arXiv.2502.06872. [cite:15]
