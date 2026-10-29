# Coding-Agent Instructions: LectureFlow Lecture-Video Assistant (Revision 2.3)

## Purpose

Extend the existing LectureFlow repository (React/Vite frontend, FastAPI backend scaffold) into a secure web application that turns an authorized lecture-video upload into a timestamped transcript, structured study notes, and lecture-grounded question answering with playable source references. Implement iteratively through the four phases below; do not build the whole system in one pass.

| Phase | Primary focus | Required outcome |
|---|---|---|
| 1 | Backend foundation on Firebase/GCP, UI wiring (no Firebase Hosting) | A deployed end-to-end application using clearly labeled processing fixtures |
| 2 | DSP, pretrained ASR, embeddings, and RAG | The same workflow operates on real lecture content |
| 3 | Evaluation-driven output improvements | Measured WER, CER, key-term, hallucination, retrieval, answer, and citation improvements |
| 4 | Optimization and release | A tested, documented, reproducible release candidate |

**Status of decisions:** The four-phase sequence is confirmed. Firebase (Authentication and Firestore) is the confirmed data/identity platform, the project targets free-tier usage, and all evaluation sets come from existing public datasets (no synthetic audio and no project-collected evaluation recordings). A self-recorded lecture is used for demonstration only. The DSP evaluation metrics are WER (with components), CER, a pre-defined key-term error rate, a non-speech hallucination rate, DNSMOS, and RTF. All other architecture choices, defaults, tests, and gates are proposed implementation instructions, not approved research thresholds or achieved-performance claims. Record any deviation before implementing it.

## Revision Log

| Area | Revision 1 | Revision 2.3 |
|---|---|---|
| Identity and data | Supabase Auth, Postgres, RLS, pgvector | Firebase Authentication, Firestore, Security Rules, Firestore vector search |
| Hosting | Vercel (Next.js) | Existing React/Vite build served via generic static host (no Firebase Hosting) |
| Job queue | PostgreSQL queue | Firestore transactional lease queue; Cloud Tasks only if a demonstrated need arises |
| DSP | Generic FFmpeg + NumPy/SciPy | Explicit, parameterized, individually bypassable chain with a defined comparison design |
| Evaluation data | WER over an unspecified set | Existing public datasets only (E1-E4); no synthetic audio; self-recorded lecture is demonstration-only |
| Evaluation metrics | WER | WER with S/D/I components, CER, key-term error rate, non-speech hallucination rate, DNSMOS, RTF |
| Cost model | Not addressed | Free-tier operating constraints, quotas, and budget alerts |

## Agent Operating Rules

1. Inspect the repository first. It currently contains `frontend/` (React 19, Vite 6, TypeScript, Tailwind 3.4, mock-only data, auth scaffolding), `backend/` (FastAPI with only `GET /api/health`), `Dockerfile`, `compose.yaml`, and `nginx.conf`. Extend working code; do not restructure without need.
2. Create `docs/development-plan.md` (mapping this brief to tasks) and `docs/phase-status.md` (current phase, evidence, blockers).
3. Work on one phase at a time with small feature branches and pull requests. Stop for owner approval at each phase boundary.
4. Do not silently substitute mocks for real processing, invent benchmark results, or report unexecuted tests as passed.
5. Do not introduce model training, a second vector database, agentic orchestration, or major infrastructure without a demonstrated need.
6. If credentials, billing, approved media, dataset access, or inference hardware are unavailable, complete safe local work and document the blocked external check.
7. Never delete existing data, rotate credentials, change billing, provision paid resources, or run destructive migrations without approval. Do not write outside the approved branch/PR scope.
8. At every handoff, report changes, affected files, executed checks, deployment status, limitations, and the next permitted task.

## Product Boundaries

### Required workflow

1. Sign in and view a private lecture library.
2. Upload a supported lecture recording and enter its title.
3. See upload progress and durable processing status.
4. Open a workspace with the original video, timestamped transcript, study notes, and question-answer interface.
5. Ask a question and receive an evidence-backed answer or an explicit insufficient-evidence response.
6. Select a source reference to seek the video to the relevant segment.
7. Export the transcript as TXT/VTT and notes as Markdown; delete a lecture and its derived data.

### Initial exclusions

- Live transcription, external URL downloading, unrestricted web retrieval.
- Training or fine-tuning ASR, embedding, or language models.
- Speaker diarization, slide OCR, visual question answering, automatic grading.
- Cross-lecture search, shared classrooms, billing, institutional administration.
- Claims of perfect transcription, guaranteed factual correctness, or understanding of slide-only information.

The audio transcript is the initial knowledge source. State that slide-only equations, diagrams, and text are outside this version's evidence coverage.

## Architecture and Contracts (Firebase Auth / GCP)

### Proposed stack

| Layer | Implementation instruction |
|---|---|
| Web | Existing React 19 + Vite + TypeScript + Tailwind app; deploy the static build via generic static hosting (no Firebase Hosting) |
| Identity | Firebase Authentication; the API verifies ID tokens with the Firebase Admin SDK |
| Data | Cloud Firestore (Native mode) with Security Rules |
| Media storage | Cloud Storage for Firebase, private bucket, owner-scoped paths |
| Vector index | Firestore vector fields and KNN `find_nearest`, executed server-side only |
| API | Python FastAPI container on Cloud Run, Pydantic validation |
| Processing | Separate Python worker on Cloud Run (Jobs or a dedicated service): FFmpeg, NumPy/SciPy, `faster-whisper`, embedding adapter |
| Language generation | Configurable pretrained model provider behind one server-side adapter |
| Quality | GitHub Actions; Ruff, Pytest, frontend lint/type/test, Firebase Emulator Suite integration tests |

Pin package versions, model identifiers/revisions, and container dependencies after compatibility testing. Inspect actual account limits during setup and record the selected region, worker configuration, storage, and upload constraints in `docs/deployment.md`.

**Deployment boundary:** Cloud Functions are not used for transcription because of execution time limits. The API creates durable jobs and returns promptly (HTTP 202); the worker processes them separately. No page request waits for transcription.

### Free-tier operating constraints

- Treat all quotas as values to verify at setup time, not guarantees. Pricing and limits change.
- Cloud Storage for Firebase requires the pay-as-you-go (Blaze) plan; free quotas remain available on it, and overage is billed. Link billing only with owner approval, set a budget alert, and document the decision.
- Select a region eligible for the free quotas of every service used, and record it.
- Enforce, from Phase 1, a maximum upload size, maximum duration, per-user lecture count, and per-user daily job limit. Reject over-limit requests with stable error codes.
- Estimate worker capacity from the *measured* real-time factor (RTF) of the chosen model on the deployed CPU configuration. Do not publish capacity figures before measurement.
- Firestore daily read/write/delete quotas are small: write segments and chunks in batches, avoid chatty listeners, and paginate reads.
- Run evaluation jobs locally or in a separately authorized workflow, not through the production free-tier worker, so evaluation does not consume the application's quota.
- Decide explicitly whether the original video is retained (required for playback) or reduced to compressed audio when storage is constrained; record the decision.

### Processing flow

```text
Browser -> Firebase Auth -> Signed upload to private bucket -> Lecture/job documents
                                                   |
                                                   v
                              Worker claims queued job (Firestore transaction + lease)
                                                   |
                    Media validation -> Audio extraction -> DSP engine (bypassable)
                                                   |
                          ASR -> Timed segments -> Timed chunks
                                                   |
                       Embeddings -> Firestore vector field
                                                   |
                           Source-linked notes -> Ready state

Question -> Ownership check -> Lecture/version-scoped vector query
         -> Evidence-constrained generation -> Citation validation
         -> Answer + server-resolved timestamps -> Video seek
```

### Suggested repository layout (extends current layout)

```text
frontend/                    # existing React/Vite app; services/mock replaced by an API client
backend/app/
  main.py  config.py  firebase.py  auth.py  contracts.py  repositories.py
  routers/                   # lectures, questions, exports
  adapters/                  # base.py, mock.py (Phase 1); real.py (Phase 2)
  fixtures/                  # labeled demonstration data
backend/worker/              # job runner and pipeline (Phase 2)
backend/tests/
eval/                        # dataset manifests, term lists, metric scripts, results (no media or dataset files committed)
firebase/                    # firestore.rules, storage.rules, firestore.indexes.json, emulator config
docs/
```

### Firestore data model

| Path | Minimum information |
|---|---|
| `lectures/{id}` | owner_id, title, storage_path, duration_s, media metadata, state, active_version, deleted_at |
| `lectures/{id}/jobs/{jobId}` | processing_version, stage, state, attempts, lease_until, worker_id, safe error_code, timings |
| `lectures/{id}/segments/{segId}` | version, order, start_s, end_s, text, diagnostic flags |
| `lectures/{id}/chunks/{chunkId}` | version, segment_ids, text, embedding (vector), embedding model/revision |
| `lectures/{id}/notes/{version}` | structured sections, supporting segment IDs, model/prompt version |
| `lectures/{id}/qa_turns/{turnId}` | question, answer_status, answer blocks, source IDs, model configuration |

Rules:

- Use opaque auto-generated IDs. Return 404 (not 403) for another user's resource.
- Keep all Firestore access inside `repositories.py`; every function takes `owner_id` and enforces it.
- Use one embedding model and vector dimension per active index. Reject incompatible query embeddings; change models only through an explicit reindexing workflow.
- Vector queries run only in server-side SDKs. Filter by lecture and processing version before nearest-neighbor selection, and create the required composite vector index in `firestore.indexes.json`. Verify prefilter behavior and dimension limits against current documentation during Phase 2.
- Use a deterministic job ID (`{lectureId}_{version}`) so repeated `upload-complete` calls cannot create duplicate active jobs.

### Job queue

Implement atomic job claiming with a Firestore transaction: a job is claimable when `queued`, or `running` with an expired lease. Add heartbeat lease renewal, a bounded attempt count, and idempotent processing steps. The Admin SDK bypasses Security Rules, so every worker read/write must enforce lecture ownership and version explicitly.

### Stable interfaces

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

Expose identical interfaces from `Mock*` and `Real*` adapters selected by validated configuration (`PROCESSING_MODE=mock|real`). Never put model-selection logic in UI components. Reject mock mode when `ENV=production`.

Answer contract (versioned): `answer_status` (`answered`, `insufficient_evidence`, `error`), lecture and version identifiers, explicit `processing_mode`, and answer blocks each referencing one or more server-issued source IDs. The server resolves IDs to segment text and timestamps. Never accept model-invented URLs, segment IDs, or timestamps.

### API behavior

| Endpoint | Required behavior |
|---|---|
| `POST /api/lectures/uploads` | Verify token; validate title, type, size; create pending lecture; return a short-lived signed upload URL for `users/{uid}/{lectureId}/source.<ext>` |
| `POST /api/lectures/{id}/upload-complete` | Verify ownership and the actual stored object (exists, size, content type); finalize; enqueue one idempotent job; return 202 |
| `GET /api/lectures` | Authenticated owner's lectures only; bounded pagination |
| `GET /api/lectures/{id}` | Authorized metadata and processing status |
| `POST /api/lectures/{id}/retry` | Retry eligible failures without duplicate active jobs |
| `GET /api/lectures/{id}/transcript` | Active transcript and processing version |
| `GET /api/lectures/{id}/notes` | Source-linked notes when available |
| `POST /api/lectures/{id}/questions` | Validate ownership/readiness; retrieve and answer within the active lecture/version |
| `GET /api/lectures/{id}/exports/{format}` | Owner-authorized TXT/VTT transcript or Markdown notes |
| `DELETE /api/lectures/{id}` | Mark inaccessible, stop work, schedule complete deletion across Firestore and Storage |
| `GET /api/health` | Health without credentials or private content (already implemented) |

Derive the owner from the verified token's `uid`, never from client input. Use `check_revoked`, distinct stable error codes (`AUTH_REQUIRED`, `SESSION_EXPIRED`, `AUTH_INVALID`), request validation, and consistent error responses.

## DSP Engine

### Design principle

The DSP engine is a hypothesis to be tested, not an assumed improvement. Modern pretrained ASR is already trained on varied audio, and speech enhancement can introduce artifacts that increase WER. Every enhancement stage must be configurable, individually bypassable, and justified by the Evaluation Plan.

### Proposed stack

| Stage | Tool (proposed default) | Notes |
|---|---|---|
| Probe and extract | FFmpeg / ffprobe via safe argument lists | Timeouts, resource limits, temp-directory cleanup; reject files without usable audio |
| Decode and I/O | `soundfile` or FFmpeg to float32 PCM | Avoid lossy re-encoding between stages |
| Resample and downmix | FFmpeg or `scipy.signal.resample_poly` | Mono, 16 kHz ASR working copy |
| High-pass filter | `scipy.signal` Butterworth (zero-phase `sosfiltfilt`) | Low cutoff (start near 80-100 Hz) to remove rumble only; tune on development data |
| Level normalization | Peak or loudness normalization (NumPy or `pyloudnorm`) | Clipping protection; no dynamic-range compression by default |
| Noise reduction (optional) | Conservative spectral gating (e.g., `noisereduce`) | Low reduction strength; disabled unless it wins in evaluation |
| Voice activity detection (optional) | Silero VAD or WebRTC VAD | Only for chunking or silence handling; must keep an offset map |
| Neural denoiser (comparison arm only) | One pretrained model (e.g., DeepFilterNet or RNNoise) | Evaluated, not enabled by default |
| Diagnostics | NumPy | Duration, sample rate, clipping fraction, silence fraction, RMS, SNR proxy, parameters, stage runtimes |

All library names are candidates. Pin versions and licenses, and confirm compatibility with the free-tier CPU worker before adoption. No stage may rely on a GPU.

### Required behaviors

- Retain the original video and a **normalized, non-enhanced baseline** (Arm A) for every processed lecture.
- Preserve original-video timing. If VAD, trimming, or chunking removes time, persist and test an explicit offset mapping before storing segments.
- Handle silent audio, stereo input, low-volume speech, noisy speech, and chunk-boundary speech without inventing transcript content.
- Record DSP configuration per processing version so results are reproducible.
- Keep the DSP step behind `AudioProcessor.process(audio_asset, config)` with a `bypass` option.

## Phase 1: Backend Foundation (Firebase)

**Goal:** Deploy a usable application with real authentication, storage, and persistence, and clearly labeled processing fixtures. Do not load inference models.

### Required tasks

- [ ] Inspect the repository; create the task map and architecture decision log, including the Supabase-to-Firebase change.
- [ ] Add `config.py`, `firebase.py`, `auth.py`, `contracts.py`, `repositories.py`, and adapter interfaces with `Mock*` implementations only.
- [ ] Initialize Firebase (Auth, Firestore, Storage, Hosting) with an emulator configuration and `.env.example` containing no secrets. Use the attached service account on Cloud Run; never commit key files.
- [ ] Write `firestore.rules` and `storage.rules` (deny direct client access to lecture data, or restrict to the owner) and `firestore.indexes.json`.
- [ ] Implement token verification, protected routes (replace the frontend's mock `AuthProvider` with Firebase Auth), session-expiry handling, and private lecture listing.
- [ ] Implement the endpoints in the API table with the signed-upload flow, server-side validation of type, size, and stored-object metadata, and quota enforcement.
- [ ] Implement the durable job document, the transactional claim function, and visible stages: `queued`, `validating`, `extracting`, `preprocessing`, `transcribing`, `indexing`, `generating_notes`, `completed`; distinguish `failed` and `cancelled`.
- [ ] Add a checked-in, authorized demonstration recording (the project's self-recorded lecture, with the speaker's consent) with aligned fixture transcript/notes/answers. Label every fixture result **Demo output — not processed from this upload**; never present fixtures as the content of an arbitrary upload. This recording is for demonstration only and must not be used in any reported evaluation metric.
- [ ] Replace `frontend/src/services/mock` calls with an API client behind the same interface; wire source clicks to video seeking and exports.
- [ ] Implement empty, loading, retryable-error, unsupported-file, expired-session, and no-evidence states, with accessible status announcements.
- [ ] Configure staging deployment (Hosting + Cloud Run), health check, environment separation, budget alert, and CI.

### Acceptance gate

- [ ] A fresh checkout builds with documented commands; Docker Compose still works.
- [ ] Staging supports sign-in, upload, refresh persistence, playback, fixture viewing, export, and deletion.
- [ ] Users A and B cannot list, read, export, or delete each other's data, verified through the API, Security Rules (Emulator), and Storage.
- [ ] Invalid uploads and failed jobs show actionable UI states without leaking exception details.
- [ ] Repeated `upload-complete` calls create one job.
- [ ] CI passes; no model inference is required.
- [ ] `docs/phase-1-report.md` records deployed URLs, executed checks, fixture boundaries, free-tier/billing status, and blockers.

**Do not start Phase 2 until the deployed shell and contracts are accepted.**

## Phase 2: DSP and Models

**Goal:** Replace fixture adapters with a real, persistent audio-to-transcript-to-RAG pipeline without redesigning the UI.

Pretrained Whisper models support an inference-first prototype rather than training a recognizer from scratch. [R1]

### Tasks

- [ ] Implement `MediaService` and the DSP engine per the DSP Engine section; produce Arm A (normalized only) and the candidate enhanced arm(s) with identical downstream settings.
- [ ] Integrate `faster-whisper` behind `Transcriber`; choose a checkpoint and compute type (e.g., int8) that fit the CPU worker. Record model/revision, device, decoding settings, language, and DSP configuration. **Measure RTF and peak memory** on the deployed worker.
- [ ] Persist ordered segments with original-timeline bounds; keep diagnostic fields without presenting them as calibrated probabilities.
- [ ] Build overlapping, segment-aware chunks preserving segment IDs and time ranges.
- [ ] Use a pinned pretrained embedding adapter and Firestore vector search; chunk size, overlap, retrieval count, and context budget are configurable.
- [ ] Constrain retrieval by owner, lecture, and active processing version before nearest-neighbor selection; verify the vector index prefilter works as designed.
- [ ] Integrate a pretrained language-model adapter with server-side secrets; answer only from retrieved evidence, else return `insufficient_evidence`.
- [ ] Validate every output source ID against retrieved evidence; resolve timestamps server-side.
- [ ] Produce source-linked structured notes; keep transcript and Q&A usable if only note generation fails.
- [ ] Prevent stale versions from replacing newer results; activate a version only after validation.
- [ ] Download the evaluation datasets (see Evaluation Plan), verify licenses and transcript quality, and write dataset manifests under `eval/`.
- [ ] Implement the metric scripts under `eval/` (WER components, CER, key-term error rate, non-speech hallucination rate, DNSMOS, RTF) with pinned versions and unit tests on hand-written examples (unit-test fixtures only).

Enhancement artifacts can worsen recognition; compare baseline and enhanced branches before choosing the default. [R2][R6]

### Acceptance gate

- [ ] A recording from the evaluation sets completes upload, DSP, ASR, indexing, notes, and grounded Q&A on the deployed worker.
- [ ] A restarted worker recovers an interrupted job through lease expiry without duplicate results; repeated requests do not duplicate segments or embeddings.
- [ ] All segments have ordered, valid bounds within the original duration; all references resolve to authorized segments.
- [ ] Silent audio and a provider timeout fail safely; no fixture is returned silently.
- [ ] A cross-user retrieval attempt returns no unauthorized content, including via the Admin SDK worker path.
- [ ] A measured baseline (all evaluation metrics on the development portions of E1-E4, stage timings, RTF, memory, observed errors) is recorded.
- [ ] `docs/phase-2-report.md` distinguishes executed from unexecuted checks and lists supported languages and limitations.

## Evaluation Plan

### Objective

Quantify whether the DSP engine improves transcription of lecture-type audio relative to a non-enhanced baseline, and under which conditions it does not or causes harm. A null or negative result is a valid, reportable outcome; the bypass default must then remain.

### Data policy

- Use only existing, publicly available datasets with human-produced reference transcripts. Do not create synthetic, noise-mixed, simulated-reverberation, or generated-speech evaluation audio, and do not rely on project-collected evaluation recordings.
- The project's self-recorded lecture is for application demonstration only and must not appear in any metric table.
- Artificial fixtures are permitted for unit tests only and must never be reported as performance evidence.
- Verify each dataset's license, redistribution terms, and transcript provenance before use. Do not commit dataset audio or transcripts to the repository; commit manifests (identifiers, splits, checksums) only.

### Experimental design

Use a **paired design**: every recording is processed under each arm with identical ASR model, revision, decoding settings, and text normalization. Only the audio-processing arm changes.

| Arm | Audio processing |
|---|---|
| A (baseline) | Mono, 16 kHz, level normalization only |
| B (conservative DSP) | A plus high-pass filter and optional conservative spectral gating |
| C (comparison) | A plus one pretrained neural denoiser (optional; for context, not default) |

### Evaluation data

| Set | Dataset | Role | Caveats |
|---|---|---|---|
| E1 (primary) | M3AV: academic lecture videos (about 367 hours across five sources covering computer science, mathematics, medicine, and biology) with human annotations of spoken words | Closest match to the product: long-form lectures with technical vocabulary and human references | Confirm the data license (the project page's Creative Commons notice may cover only the page template). Confirm transcript quality on a sample. Select a manageable subset and record it in a manifest. |
| E2 | ACL 60/60 evaluation talks: technical presentations with human post-edited transcripts | A second long-form technical-speech source | English conference talks, likely clean. Verify the license. |
| E3 | TED-LIUM 3 dev/test talks with manual transcripts (the legacy TED-LIUM 2 dev/test talks) | Spontaneous lecture-style speech with a published ASR benchmark | CC BY-NC-ND 3.0 (non-commercial, no derivatives): confirm that the processing is permitted. Do not use the automatically generated training transcripts as references. Corpus paper is outside the 2021-2026 window (dataset citation only). |
| E4 (robustness) | Loquacious Set dev and test portions (mixed clean, noisy, read, spontaneous, and talk speech; component licenses permit research and commercial use) | Noisy-condition check, where DSP is most likely to matter | Segments are short (up to about 40 s) and not lecture-specific; spontaneous speech is a small share. Report separately from E1-E3. Filter or bin by condition. |

Notes:

- Report each set separately. Do not pool sets, and do not generalize public-set results to the deployment's own rooms and microphones; state this limitation in the report.
- Public talks may overlap with pretrained-ASR training data (the training data of the ASR model may not be fully disclosed), which could lower baseline error rates and compress differences. Disclose this for every set.
- Freeze a development subset and a separate held-out subset within each set before any tuning. Tune DSP parameters on development subsets only.
- Record provenance, licenses, normalization policy, selected subsets, and sample counts. Report missing coverage (languages, accents, room types, noise types).
- If a dataset's references prove unreliable on inspection (for example, automatic transcripts), exclude it or report it as unreliable rather than using it as ground truth.

### Conditions without synthetic degradation

Because no noise is added, measure condition from the recordings themselves. Compute per-recording diagnostics (SNR proxy, clipping fraction, silence fraction, RMS, optional reverberation proxy), group recordings into pre-declared bins (for example clean, moderate, noisy), and report paired results per bin. State that this design cannot establish error rate as a function of controlled SNR.

### Metrics

All text metrics use one fixed, documented normalization policy (casing, punctuation, numerals, contractions), applied identically to references and hypotheses in every arm, with pinned library versions (e.g., `jiwer`).

| Metric | Definition | How to compute and report |
|---|---|---|
| WER (primary) | (Substitutions + deletions + insertions) / reference words | Report S, D, and I rates separately. Rising deletions can indicate over-suppression; rising insertions can indicate hallucination on non-speech |
| CER | Character-level edit distance / reference characters | Same normalization and alignment tooling as WER. Useful for technical terms, identifiers, and spelling-level changes. Report with WER |
| Key-term error rate (KTER) | Share of reference occurrences of pre-defined key terms that are not correctly transcribed | See "Key-term list" below |
| Non-speech hallucination rate (NSHR) | Share of naturally occurring non-speech segments for which the ASR outputs any non-empty text after normalization | See "Non-speech segments" below |
| DNSMOS | Non-intrusive predicted quality scores for speech (SIG), background noise (BAK), and overall (OVRL), each on a 1-5 scale, using the DNSMOS P.835 model | Compute on the audio each arm sends to the ASR, at the model's required sample rate, with a pinned model version. Supplementary: no pass/fail threshold. Report the correlation between DNSMOS change and WER change |
| RTF | Processing time / audio duration | See "RTF" below |
| Delta metric | Metric(Arm A) minus metric(Arm B) per set and bin; positive means DSP helped (for error metrics) | Paired bootstrap confidence interval resampled over recordings (or fixed-length segments for long-form audio); report counts. Call a change "supported" only if the interval excludes zero |
| Signal diagnostics | Clipping, silence, RMS, SNR proxy per recording | Used for binning and explanation, not as outcome metrics |

#### Key-term list

- Define, before running any arm, a frozen list of key terms per dataset: domain-specific terms, proper nouns, acronyms, and numerals that carry lecture content. Derive the list by a documented rule applied to the reference transcripts (and, for E1, the dataset's own annotated vocabulary or slide text if available), then have a person review it. Record the rule, the list, and the reviewer.
- Do not use hypotheses from any arm to build or adjust the list.
- Count a term as correct when the normalized hypothesis contains it at the aligned position (exact match after normalization). Report the number of reference term occurrences, so the denominator is visible.
- E4 (short mixed-domain clips) may have too few key terms; report KTER for E4 only if the counts are adequate, otherwise state that it is not applicable.

#### Non-speech segments

- Use only naturally occurring non-speech regions already present in the evaluation datasets (for example, gaps between annotated utterances such as silence, applause, music, or room noise, identified from reference timestamps). Do not insert, generate, or splice silence or noise.
- Apply a documented minimum duration and a safety margin from neighboring speech, and record the selection rule and the number of segments per set.
- NSHR = segments with non-empty ASR output / total non-speech segments. Also report inserted words per minute of non-speech audio, and flag repeated-phrase looping.
- Run the ASR on each non-speech segment (or the corresponding region of the processed audio) under every arm, with identical settings. Where timestamps are unreliable or too few segments exist, report NSHR as not evaluable for that set rather than estimating it.
- Interpret both directions: DSP stages such as VAD or silence trimming may reduce NSHR, while noise reduction artifacts may raise it.

#### RTF

- RTF = total processing time / input audio duration, measured on the same hardware, with warm and cold runs distinguished.
- Report RTF per stage (extraction, DSP, ASR) and in total for each arm, plus DSP overhead = RTF(Arm B) minus RTF(Arm A). Record hardware, CPU count, memory, model/revision, compute type, and sample count.
- Treat RTF as a cost metric, not a quality metric. Agree an RTF budget with the owner after the Phase 2 baseline, given the free-tier worker.

Retrieval, answer, citation, abstention, and notes metrics (Recall@k, human-reviewed correctness and unsupported-claim rate, valid-ID rate, citation precision, claim coverage, false refusal) need question and evidence annotations that the transcription datasets do not provide. For these, use a small question set written and annotated over transcripts of E1 lectures, documenting the annotation procedure, answerability labels, and reference segments; label it as a project-created annotation layer over existing data, and report its size. Evaluate retrieval and answer quality separately. [R3] Citation presence is not evidence support. [R4]

### Decision rule

- Enable a DSP stage by default only if it yields a supported WER improvement on development subsets for the target bins **and** does not regress, beyond a tolerance agreed with the owner: clean-bin WER, CER, KTER, or NSHR.
- DNSMOS gains alone never justify enabling a stage. A stage that improves DNSMOS but not WER stays disabled.
- If enhancement helps only in the noisy bin, make it conditional on measured diagnostics or leave it opt-in.
- A stage whose DSP overhead exceeds the agreed RTF budget stays disabled or opt-in, even if it improves WER.
- Set numeric targets and tolerances for the metrics with the project owner after the Phase 2 baseline and freeze them before final evaluation. Until then, label results as measured comparisons, not validated passes.
- With small samples, disclose counts and avoid unsupported generalization.

### Deliverables

`docs/evaluation-protocol.md` (design, data, normalization, metric definitions and denominators, key-term list rule, non-speech selection rule, decision rule), dataset manifests, the frozen key-term lists, machine-readable per-recording results (CSV/JSON with set, arm, bin, and each metric), a reproducible script in `eval/` that regenerates all tables, and a results section stating what changed, counts, intervals, and failures.

## Phase 3: Output Quality

**Goal:** Improve information delivered to students using measured comparisons, not UI polish alone.

- [ ] Freeze development and held-out subsets and the key-term lists (see Evaluation Plan).
- [ ] Run the A/B(/C) comparison on all metrics; keep a bypass where enhancement regresses.
- [ ] Improve decoding, chunk boundaries, repetition handling, and technical-term hints without inventing lecture content; track NSHR and looping when changing decoding settings.
- [ ] Tune chunk size, overlap, retrieval count, context ordering, and the insufficient-evidence rule on the development subset only.
- [ ] Add reranking or hybrid retrieval only after a documented failure case and measured benefit.
- [ ] Improve notes (headings, key points, source-linked definitions) without slide-only or unspoken material.
- [ ] Support multi-segment answers, same-lecture follow-ups (history clarifies the query but is not evidence), and uncertainty/coverage notices without uncalibrated confidence percentages.
- [ ] Test source-click seeking, VTT alignment, long-transcript rendering, empty retrieval, and evidence spanning chunk boundaries.

### Acceptance gate

- [ ] A reproducible comparison shows what changed from Phase 2 and whether each change improved its intended metric.
- [ ] The held-out subsets were not used for repeated tuning; any contamination is disclosed.
- [ ] Reference-resolution and malformed-citation contract tests pass.
- [ ] Human review covers answer support, note support, abstention behavior, and playback alignment.
- [ ] `docs/phase-3-report.md` lists improvements, regressions, and categorized remaining failures.

## Phase 4: Optimization and Release

**Goal:** Stabilize, optimize demonstrated bottlenecks, and prepare an honest, reproducible handoff.

- [ ] Profile before optimizing; separate extraction, DSP, ASR, embedding, retrieval, and generation costs.
- [ ] Reuse loaded models within the worker's memory budget; tune concurrency only after correctness checks.
- [ ] Cache transcripts, embeddings, and notes by content and configuration within one owner's scope; never expose cross-user cache hits or stale versions.
- [ ] Improve large-file upload reliability (resumable uploads), cancellation, bounded retries, and measured (not guessed) progress.
- [ ] Add request-size bounds, upload quotas, per-user rate limits, provider timeouts, and token budgets; monitor free-tier consumption against the budget alert.
- [ ] Paginate or virtualize long transcripts where profiling shows need; finish keyboard, mobile, and accessibility testing.
- [ ] Review Security Rules, indexes, orphan cleanup, dependency risks, and secret handling.
- [ ] Implement and test deletion across Storage, jobs, segments, chunks/vectors, notes, and Q&A history; deletion must prevent new work from recreating artifacts.
- [ ] Keep signed URLs short-lived; document the expiry window and do not promise instant revocation.
- [ ] Re-run functional, isolation, security, quality, and deployment checks on the release candidate; publish setup, architecture, environment, model/license, deployment, evaluation, limitations, rollback, and demo instructions.

### Acceptance gate

- [ ] A clean installation works from documented configuration.
- [ ] Production runs real processing, rejects mock mode, and exposes no privileged secrets.
- [ ] Upload-to-answer, playback references, exports, retry, deletion, and worker-restart recovery pass on the target deployment.
- [ ] All mandatory automated checks pass; unexecuted external checks are listed, not marked passed.
- [ ] Before/after results are reproducible with versions and observed resource constraints.
- [ ] Tagged commit, deployment record, rollback procedure, and owner-approved limitations exist.

## Security Throughout Development

RAG introduces privacy and adversarial risks; treat lecture text and retrieved passages as untrusted data, not instructions. [R5]

- Enforce owner isolation on metadata, storage, transcripts, embeddings, retrieval, exports, playback, and Q&A history from Phase 1.
- Verify Firebase ID tokens at the API (with revocation checking); never authorize from client-controlled IDs.
- Write Security Rules that deny by default and test them with the Emulator. Audit every Admin SDK path, because it bypasses rules.
- Keep service-account credentials and model-provider keys server-side only; never commit or log them.
- Authorize before issuing short-lived signed URLs; keep the bucket private.
- Treat filenames and transcript text as untrusted: no shell interpolation, unsafe rendering, or prompt-controlled tool access.
- Instruct generation to ignore instructions embedded in lecture evidence; add injection tests.
- Use approved recordings only; obtain the speaker's consent for the demonstration recording; disclose external provider processing and obtain permission first. Respect dataset licenses and redistribution limits for public evaluation sets.
- Log request/job IDs, stages, safe error codes, and timings; avoid logging lectures, questions, tokens, or signed URLs.
- Do not claim ISO certification, accessibility conformance, or production-grade security solely because checks pass.

## CI/CD and Evidence

```bash
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend test
ruff check backend eval
ruff format --check backend eval
pytest backend/tests eval/tests
firebase emulators:exec "pytest backend/tests/integration"
```

Document equivalents if scripts differ. Require these on pull requests; pin Python/Node versions and commit lockfiles. Run deterministic unit and contract tests with identified fixtures; do not download large models or evaluation corpora on every pull request. Run Security Rules and Firestore integration tests against the Emulator, never the live project. Place real-model, deployed-worker, and evaluation runs in a separately authorized workflow. Add a regression test for each discovered privacy, timestamp, retrieval, or job-recovery defect. Keep staging and production projects, buckets, and secrets separate.

## Handoff and Starting Instruction

Every phase report contains: scope completed, changed modules, exact test commands and results, deployment verification, evidence files, known limitations, unresolved approvals, and the proposed next step, plus a reproducible demo path.

**Start now:** Inspect the repository and produce the Phase 1 task map. Implement only Phase 1 until its acceptance gate has been reviewed.

## References

Academic sources (IEEE or open access, 2021-2026 unless noted; preprints labeled). Platform documentation and dataset pages are cited only for tool and data behavior and are not peer-reviewed. Verify every bibliographic detail before submission.

**R1.** A. Radford et al., "Robust Speech Recognition via Large-Scale Weak Supervision," in *Proc. 40th Int. Conf. Machine Learning*, PMLR vol. 202, pp. 28492-28518, 2023. https://proceedings.mlr.press/v202/radford23a.html

**R2.** T. Ochiai et al., "Rethinking Processing Distortions: Disentangling the Impact of Speech Enhancement Errors on Speech Recognition Performance," arXiv:2404.14860, 2024 (preprint). https://doi.org/10.48550/arXiv.2404.14860

**R3.** S. Es, J. James, L. Espinosa Anke, and S. Schockaert, "RAGAs: Automated Evaluation of Retrieval Augmented Generation," in *Proc. EACL: System Demonstrations*, pp. 150-158, 2024. https://doi.org/10.18653/v1/2024.eacl-demo.16

**R4.** T. Gao, H. Yen, J. Yu, and D. Chen, "Enabling Large Language Models to Generate Text with Citations," in *Proc. EMNLP*, pp. 6465-6488, 2023. https://doi.org/10.18653/v1/2023.emnlp-main.398

**R5.** B. Ni et al., "Towards Trustworthy Retrieval Augmented Generation for Large Language Models: A Survey," arXiv:2502.06872, 2025 (preprint). https://doi.org/10.48550/arXiv.2502.06872

**R6.** "When De-noising Hurts: A Systematic Study of Speech Enhancement Effects on ASR," arXiv:2512.17562, 2025 (preprint; authors and full title to be verified). https://arxiv.org/abs/2512.17562

**R7.** C. K. A. Reddy, V. Gopal, and R. Cutler, "DNSMOS P.835: A Non-Intrusive Perceptual Objective Speech Quality Metric to Evaluate Noise Suppressors," in *Proc. IEEE ICASSP*, 2022, pp. 886-890. http://ieeexplore.ieee.org/document/9746108/ (also arXiv:2110.01763).

**R8.** "Investigation of Whisper ASR Hallucinations Induced by Non-Speech Audio," arXiv:2501.11378, 2025 (preprint; authors to be verified). https://www.alphaxiv.org/abs/2501.11378

**R9.** "An Analysis of Semantic Metrics Beyond WER," arXiv:2609.21663, 2026 (preprint; authors to be verified). https://arxiv.org/html/2609.21663v1 (cited for the limits of WER and the value of complementary metrics such as CER).

**D1 (E1).** Z. Chen et al., "M3AV: A Multimodal, Multigenre, and Multipurpose Audio-Visual Academic Lecture Dataset," ACL 2024 (identifiers such as arXiv:2403.14168 to be verified). Project page: https://jack-zc8.github.io/M3AV-dataset-page/

**D2 (E2).** ACL 60/60 evaluation sets, IWSLT 2023 multilingual track; Hugging Face `ymoslem/acl-6060` (2025). Verify license.

**D3 (E3, outside date range).** F. Hernandez et al., "TED-LIUM 3: Twice as Much Data and Corpus Repartition for Experiments on Speaker Adaptation," arXiv:1805.04699. Dataset citation only; CC BY-NC-ND 3.0.

**D4 (E4).** T. Parcollet, Y. Tseng, S. Zhang, and R. van Dalen, "Loquacious Set: 25,000 Hours of Transcribed and Diverse English Speech Recognition Data for Research and Commercial Use," in *Proc. Interspeech*, 2025 (DOI to be verified). https://www.isca-archive.org/interspeech_2025/parcollet25_interspeech.pdf

**Platform documentation (non-academic):** Firebase Authentication, "Verify ID Tokens"; Firebase, "Introduction to the Admin Cloud Storage API"; Firebase Pricing and Cloud Storage billing requirements; Firestore vector search documentation. Verify current limits at setup time.
