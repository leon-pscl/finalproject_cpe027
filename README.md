# LectureFlow
<<<<<<< HEAD

# LectureFlow is a lecture transcription prototype organized as separate frontend and backend applications:

## What this project is

LectureFlow is a lecture transcription prototype that records, transcribes, and optionally enhances audio lectures.

## Program flow

1.  **Upload** – Frontend sends audio via `POST /api/transcriptions` (multipart file) or `POST /api/lectures` (lecture metadata) to the FastAPI backend.
2.  **Optional DSP** – If `ENHANCE_AUDIO=true`, the backend runs the DSP engine (`backend/app/dsp.py`) to clean up the recording before transcription. This stage reduces environmental noise and reverberation to improve ASR accuracy. (See [DSP speech enhancement](#dsp-speech-enhancement-off-by-default) for details).
3.  **ASR** – The (local) Whisper model is invoked through the `faster-whisper` library (`WHISPER_MODEL` env var) to produce a transcript.
4.  **Storage & Retrieval** – Transcripts are stored and served via `GET /api/transcriptions/{id}` and `GET /api/lectures/{id}`. Embeddings are created with MiniLM‑L6‑v2 (`sentence‑transformers`) and indexed in a FAISS‑CPU vector store.
5.  **RAG Generation** – The `/api/rag` endpoint (or `GET /api/answers`) calls the OpenAI `gpt‑4o‑mini` model with a grounding prompt, falling back to pure passage retrieval when the API key is missing.
6.  **Health & Utils** – `GET /api/health` reports service status; other utility endpoints manage uploads, deletion, and worker status.

## Libraries / Dependencies

 <!-- AUTO-DEP-TABLES START -->

_This section is generated automatically from `frontend/package.json`, `backend/requirements.txt`, and `eval/requirements.txt` by the helper script `scripts/update_deps_readme.py`._

 <!-- AUTO-DEP-TABLES END -->

## How to run

```sh
docker compose up --build -d   # start both services
# Run ngrok to expose the frontend port (default 8080):
#   ngrok http 8080   # then use the generated public URL for remote demo
```

Or for local development:

```sh
# frontend
cd frontend && npm ci && npm run dev
# backend
cd backend && python -m venv .venv && .\.venv\Scripts\Activate.ps1 && pip install -r requirements.txt && uvicorn app.main:app --reload
```

## How to get evaluation metrics values

Run the evaluation CLI:

```sh
python eval/cli.py   # generates results in eval/results/
```

## Datasets used (and purpose)

- **M3AV** – Multimodal Academic Lecture Dataset (audio‑visual, transcripts). Project page: https://jack-zc8.github.io/M3AV-dataset-page/
- **ACL 60/60** – IWSLT 2023 multilingual evaluation talks. Hugging Face: https://huggingface.co/datasets/ymoslem/acl-6060
- **Loquacious** – Short, diverse English speech clips for robustness testing. Interspeech 2025 paper (PDF): https://www.isca-archive.org/interspeech_2025/parcollet25_interspeech.pdf
- **DEMAND** – Environmental noise recordings (CC BY‑SA 3.0). Zenodo: https://zenodo.org/record/1227120
- **MUSAN** – Music, speech and noise corpus for noise addition. OpenSLR: https://www.openslr.org/17/

67
LectureFlow is a lecture transcription prototype organized as separate frontend and backend applications:
<<<<<<< HEAD

- `ngrok` can expose the local dev server publicly for demos. Install with `npm i -g ngrok` and run `ngrok http 8000` (or the port your backend runs on). The generated URL can be shared for the final demo.
- `backend/` — a Python/FastAPI API scaffold, independently runnable and containerized.

## Docker

Start both services:

```sh
docker compose up --build -d
```

Open `http://localhost:8080` on the host. On another device on the same network, open `http://<host-LAN-IP>:8080`. On Windows, find the host IPv4 address with `ipconfig`. The network must allow device-to-device connections, and the host firewall must allow inbound TCP on the selected port.

The frontend container serves the built app and proxies `/api/` requests to FastAPI. The API is available through the frontend at `http://localhost:8080/api/health`. The backend port is not published directly to the host.

Use another host port when 8080 is occupied:

```powershell
$env:APP_PORT = "8090"
docker compose up --build -d
```

Stop services with `docker compose down`.

## Local development

Frontend:

```powershell
cd frontend
npm ci
npm run dev
```

Backend (in a separate terminal):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Vite proxies `/api/` calls to the local backend at port 8000. FastAPI's interactive API documentation is available at `http://localhost:8000/docs`.

## Speech recognition (real, pretrained)

The backend runs a pretrained Whisper model through [faster-whisper](https://github.com/SYSTRAN/faster-whisper). No training is involved. The model downloads automatically on the first transcription (internet needed once) and is cached in the `model-cache` Docker volume (or `MODEL_CACHE_DIR` locally).

| Variable               | Default | Notes                                                                 |
| ---------------------- | ------- | --------------------------------------------------------------------- |
| `WHISPER_MODEL`        | `small` | `tiny`/`base` faster, `medium`/`large-v3` more accurate (GPU advised) |
| `WHISPER_LANGUAGE`     | `auto`  | set `en` or `tl` to force a language                                  |
| `WHISPER_COMPUTE_TYPE` | `int8`  | use `float16` on GPU                                                  |
| `MAX_UPLOAD_MB`        | `512`   |                                                                       |

```sh
WHISPER_MODEL=base docker compose up --build -d     # PowerShell: $env:WHISPER_MODEL="base"
```

API: `POST /api/transcriptions` (multipart `file`) -> job id; `GET /api/transcriptions/{id}` -> status, progress, segments; `DELETE` removes it. The server deletes the raw audio as soon as processing ends.

Recordings uploaded through `POST /api/lectures/...` are queued and processed by a worker inside the API process (media/DSP, then ASR, then `GET /api/lectures/{id}` reports `completed`). Set `WORKER_ENABLED=false` to disable it.

Backend tests: `cd backend && pip install -r requirements-dev.txt && pytest` (stub model; no download needed).

## DSP speech enhancement (off by default)

`backend/app/dsp.py` implements a classical signal processing engine (no learned models) to improve speech quality before ASR.

### How the DSP Engine Works

=======
=======
 
 ## What this project is
 
 LectureFlow is a lecture transcription prototype that records, transcribes, and optionally enhances audio lectures.
 
 ## Program flow
 
 1. **Upload** – Frontend sends audio via `POST /api/transcriptions` (multipart file) or `POST /api/lectures` (lecture metadata) to the FastAPI backend.
 2. **Optional DSP** – If `ENHANCE_AUDIO=true`, the backend runs the DSP engine (`backend/app/dsp.py`) to clean up the recording before transcription. This stage reduces environmental noise and reverberation to improve ASR accuracy. (See [DSP speech enhancement](#dsp-speech-enhancement-off-by-default) for details).
 3. **ASR** – The (local) Whisper model is invoked through the `faster-whisper` library (`WHISPER_MODEL` env var) to produce a transcript.
 4. **Storage & Retrieval** – Transcripts are stored and served via `GET /api/transcriptions/{id}` and `GET /api/lectures/{id}`. Embeddings are created with MiniLM‑L6‑v2 (`sentence‑transformers`) and indexed in a FAISS‑CPU vector store.
 5. **RAG Generation** – The `/api/rag` endpoint (or `GET /api/answers`) calls the OpenAI `gpt‑4o‑mini` model with a grounding prompt, falling back to pure passage retrieval when the API key is missing.
 6. **Health & Utils** – `GET /api/health` reports service status; other utility endpoints manage uploads, deletion, and worker status.
 
 
 ## Libraries / Dependencies
 
 <!-- AUTO-DEP-TABLES START -->
 *This section is generated automatically from `frontend/package.json`, `backend/requirements.txt`, and `eval/requirements.txt` by the helper script `scripts/update_deps_readme.py`.*
 <!-- AUTO-DEP-TABLES END -->
 
 
 ## How to run
 
 ```sh
 docker compose up --build -d   # start both services
 # Run ngrok to expose the frontend port (default 8080):
 #   ngrok http 8080   # then use the generated public URL for remote demo
 ```
 Or for local development:
 
 ```sh
 # frontend
 cd frontend && npm ci && npm run dev
 # backend
 cd backend && python -m venv .venv && .\.venv\Scripts\Activate.ps1 && pip install -r requirements.txt && uvicorn app.main:app --reload
 ```
 
 ## How to get evaluation metrics values
 
 Run the evaluation CLI:
 
 ```sh
 python eval/cli.py   # generates results in eval/results/
 ```
 
 ## Datasets used (and purpose)
 
 - **M3AV** – Multimodal Academic Lecture Dataset (audio‑visual, transcripts). Project page: https://jack-zc8.github.io/M3AV-dataset-page/
 - **ACL 60/60** – IWSLT 2023 multilingual evaluation talks. Hugging Face: https://huggingface.co/datasets/ymoslem/acl-6060
 - **Loquacious** – Short, diverse English speech clips for robustness testing. Interspeech 2025 paper (PDF): https://www.isca-archive.org/interspeech_2025/parcollet25_interspeech.pdf
 - **DEMAND** – Environmental noise recordings (CC BY‑SA 3.0). Used as the noise bank to generate synthetic noisy samples; each environment name (e.g., `DKITCHEN`, `OOFFICE`) populates the `environment` column in the benchmark manifest. If the harness is invoked with an explicit `envs` list, the selection is deliberate; otherwise environments are randomly sampled from the full DEMAND set. Zenodo: https://zenodo.org/record/1227120
 - **MUSAN** – Music, speech and noise corpus for noise addition. OpenSLR: https://www.openslr.org/17/
 
 67
 LectureFlow is a lecture transcription prototype organized as separate frontend and backend applications:
 
 - `ngrok` can expose the local dev server publicly for demos. Install with `npm i -g ngrok` and run `ngrok http 8000` (or the port your backend runs on). The generated URL can be shared for the final demo.
 - `backend/` — a Python/FastAPI API scaffold, independently runnable and containerized.
 
 ## Docker
 
 Start both services:
 
 ```sh
 docker compose up --build -d
 ```
 
 Open `http://localhost:8080` on the host. On another device on the same network, open `http://<host-LAN-IP>:8080`. On Windows, find the host IPv4 address with `ipconfig`. The network must allow device-to-device connections, and the host firewall must allow inbound TCP on the selected port.
 
 The frontend container serves the built app and proxies `/api/` requests to FastAPI. The API is available through the frontend at `http://localhost:8080/api/health`. The backend port is not published directly to the host.
 
 Use another host port when 8080 is occupied:
 
 ```powershell
 $env:APP_PORT = "8090"
 docker compose up --build -d
 ```
 
 Stop services with `docker compose down`.
=======
>>>>>>> for-demo

LectureFlow turns a lecture recording into a searchable, question-answerable transcript.
It is a two-part application: a React/Vite frontend and a Python/FastAPI backend, each
independently runnable and containerized.

The pipeline is: **upload → media extraction → DSP → ASR → chunk → embed → FAISS index →
retrieval → grounded LLM answer**. Everything below describes that path as the code
actually implements it.

<<<<<<< HEAD
Recordings uploaded through `POST /api/lectures/...` are queued and processed by a worker inside the API process (media/DSP, then ASR, then `GET /api/lectures/{id}` reports `completed`). Set `WORKER_ENABLED=false` to disable it.
 
 Backend tests: `cd backend && pip install -r requirements-dev.txt && pytest` (stub model; no download needed).
 
 ## DSP speech enhancement (off by default)
 
 `backend/app/dsp.py` implements a classical signal processing engine (no learned models) to improve speech quality before ASR. 
 
 ### How the DSP Engine Works
>>>>>>> refs/remotes/origin/main
The pipeline processes audio in 90-second blocks to manage memory and track non-stationary noise:

1. **Preprocessing**: DC offset removal and a 4th-order Butterworth high-pass filter (default 80 Hz) to remove low-frequency rumble.
2. **Time-Frequency Analysis**: A Short-Time Fourier Transform (STFT) with a 512-point Hann window and 75% overlap converts the signal into the frequency domain.
3. **Noise Estimation**: The engine uses a Voice Activity Detector (VAD) to distinguish speech from noise. It estimates the Noise Power Spectral Density (PSD) using a combination of:
   - **Minimum Statistics**: Tracks the minimum power in each frequency bin over time to follow slow-changing noise.
   - **VAD-held Estimate**: Captures the noise spectrum from the most recent non-speech frames.
4. **Cleaning Methods**:
   - **Wiener Filtering (Default)**: Applies a decision-directed Wiener gain based on the a-priori SNR (Ephraim-Malah model). This is highly effective for stationary and semi-stationary noise.
   - **Spectral Subtraction**: An alternative Fourier-based method that subtracts the median noise PSD from the signal spectrum. This is computationally lighter and useful for consistent background hums.
   - **Dereverberation (Optional)**: Uses a Lebart/Habets exponential-decay model to estimate late reverberation PSD and attenuate it, reducing the "echo" effect of large rooms.
5. **Reconstruction**: The cleaned complex STFT is converted back to time-domain audio via Inverse STFT (ISTFT) and overlap-add.
6. **Normalization**: Final loudness normalization to -20 dBFS RMS with peak limiting to ensure consistent volume.

| Variable            | Default  | Meaning                                                 |
| ------------------- | -------- | ------------------------------------------------------- |
| `ENHANCE_AUDIO`     | `false`  | enable dsp.py before ASR for `POST /api/transcriptions` |
| `DSP_METHOD`        | `wiener` | cleaning algorithm: `wiener` or `spectral_subtraction`  |
| `DSP_REVERB_WEIGHT` | `0.0`    | `0` = denoise only; `0.3-0.6` adds la dereverberation   |
| `DSP_RT60`          | `0.5`    | assumed room reverberation time (s)                     |
| `DSP_FLOOR_DB`      | `-15`    | maximum attenuation (limits musical noise)              |

**Measure it, do not assume it helps.** Put a recording and a correct transcript in `./samples/`, then:

```sh
sudo docker-compose -f compose.yaml exec backend python -m app.evaluate \
  --audio /samples/lecture.m4a --reference /samples/lecture.txt --terms /samples/terms.txt --out /samples/results
```

It runs the same Whisper model on raw / denoised / denoised+dereverberated audio and prints WER, CER, technical-term accuracy and time, and saves the enhanced WAVs so you can listen.

## Recent Progress

- Backend foundation, storage adapters, and worker pipeline wired (upload → DSP → ASR) and verified.
- DSP engine integrated with optional ENHANCE_AUDIO flag.
- RAG pipeline (FAISS vector store, OpenAI answer generator) implemented and unit‑tested.
- Evaluation harness scaffold (`eval/` package) ready; key scripts added.
- Frontend upload UI works with progress display; 6/8 frontend tests passing.
- Pending: full Step 5A dataset run, chunking/embeddings (Step 6), RAG answer generation (Step 7), and deployment tasks.
=======
---

## 1. Architecture at a glance

```
              ┌──────────── frontend (React + Vite, nginx in prod) ────────────┐
              │ NewRecordingPage → uploadLecture() → poll → RightPanel (Q&A)   │
              └──────────────────────────────┬────────────────────────────────-┘
                                             │  /api/*  (nginx proxy or Vite dev proxy)
              ┌──────────────────────────────▼─────────────────────────────────┐
              │                   FastAPI app (backend/app)                    │
  routers/    │ lectures  storage  dsp  notes  qa  delete  health              │
              │                                + /api/transcriptions           │
  services/   │ LectureService  (quotas, signed URLs, job creation)            │
  repositories│ LectureRepository  (InMemory | Firestore)  ← job state, leases │
  storage     │ StorageAdapter     (LocalStorage | Firebase)  ← bytes          │
              │                                                                │
  worker.py   │ PipelineWorker → media.py (ffmpeg DSP) → asr.py → chunker.py   │
              │                → embedder.py → vector_store.py (FAISS)         │
              └────────────────────────────────────────────────────────────────┘
```

Two independent ingestion paths exist, and they do **not** share the same DSP code:

|  | Lecture pipeline (primary) | Direct transcription (demo / eval) |
|---|---|---|
| Entry | `POST /api/lectures/uploads` → signed PUT → `POST /api/lectures/{id}/upload-complete` | `POST /api/transcriptions` (multipart) |
| Queue | repository job doc + `PipelineWorker` claim/lease | in-process `JobStore` thread pool (`jobs.py`) |
| DSP | `media.py` — ffmpeg filter graph, gated by `DSP_ENABLED` | `dsp.py` — scipy Wiener enhancer, gated by `ENHANCE_AUDIO` |
| Output | transcript + chunks + FAISS index in storage | transcript held in memory, TTL-expired |
| Status | `GET /api/lectures/{id}` | `GET /api/transcriptions/{id}` |

---

## 2. Input stage

### 2.1 Client side

`frontend/src/pages/NewRecordingPage.tsx` is a file picker (`.wav,.mp3,.m4a,audio/*`) —
there is no in-browser `MediaRecorder` capture; the user supplies an existing file.

`uploadLecture()` in `frontend/src/services/api.ts` performs the three-step upload and
reports a `phase` (`initiating → uploading → completing → polling`) through `onProgress`:

1. `POST /api/lectures/uploads` with `{title, declared_type, declared_size_bytes}`.
2. `PUT` the raw bytes to the returned `signed_upload_url` (XHR, so byte-level progress works).
3. `POST /api/lectures/{id}/upload-complete` with `{storage_path, observed_size_bytes, observed_content_type}`.

`pollLectureForCompletion()` then polls `GET /api/lectures/{id}` with exponential backoff
(1 s → 5 s cap) until the state is `completed`, `failed` or `cancelled`.

### 2.2 Server side — `services/lecture_service.py`

`initiate_upload` validates before a single byte is accepted:

- content type must be in `SUPPORTED_CONTENT_TYPES` → else `UNSUPPORTED_FILE`
- `declared_size_bytes` ≤ `MAX_UPLOAD_MB` → else `FILE_TOO_LARGE`
- active lecture count < `PER_USER_LECTURE_LIMIT` → else `QUOTA_EXCEEDED`

It then mints `lecture_id = uuid4().hex`, reserves
`users/{owner_id}/{lecture_id}/source{ext}` and returns an HMAC-signed upload URL.

`complete_upload` re-checks the storage path against the reserved one
(`STORED_OBJECT_MISMATCH`), verifies the stored object's size and content type, and
creates the job document with a **deterministic job id** derived from
`(lecture_id, processing_version)` — so a duplicate `upload-complete` cannot start a
second job for the same version.

### 2.3 Storage and signing — `storage.py`

`LocalStorageAdapter` (default for dev) writes under `LOCAL_STORAGE_ROOT`, stores a
sidecar `*.metadata.json` for the content type, and signs URLs as
`HMAC(secret, storage_path + expiry)`. `routers/storage.py` serves
`PUT /api/storage/upload/{path}` and verifies the signature before writing.
`FirebaseStorageAdapter` is the production alternative (GCS signed URLs).
Path traversal is rejected by `_safe_storage_path`.

### 2.4 Identity

`auth.py::verify_id_token` is meant to verify a Firebase ID token and derive the owner id
from the verified `uid` only. **In the current demo build it short-circuits and returns
`VerifiedUser(uid="demo_user")` for any non-empty bearer token.** All data is therefore
owned by a single synthetic user. See [Known gaps](#9-known-gaps).

---

## 3. DSP processing stage

### 3.1 Lecture pipeline DSP — `media.py` (ffmpeg)

`PipelineWorker._run_media` → `LocalMediaService.validate_and_extract` →
`process_local_audio`. All ffmpeg invocations are argument lists with explicit timeouts
(no shell), and `ffprobe` runs first so duration can be rejected before decoding.

1. **Probe** (`probe_media`) — format, duration, sample rate, channels, codec.
   Duration over `max_duration_minutes` aborts the job.
2. **Arm A baseline** (`extract_arm_a`) — *always* runs, even when DSP is bypassed:
   `-vn -sn -dn -map 0:a:0 -ac 1 -ar 16000 -af loudnorm=I=-20:TP=-2:LRA=7 -c:a pcm_f32le`.
   This is the reference condition used by the evaluation harness.
3. **DSP stages** — skipped entirely when `DSPConfig.bypass` is true (`DSP_ENABLED=false`),
   in which case Arm A is copied to the DSP output. When enabled, each stage is a separate
   ffmpeg pass whose runtime is recorded:

   | Stage | Filter | Gate |
   |---|---|---|
   | High-pass | `highpass=f=80,areverse,highpass=f=80,areverse` (forward + reverse → zero phase) | always on when DSP enabled |
   | Spectral gating | `afftdn=nf=-25` | `DSP_SPECTRAL_GATING_ENABLED` |
   | Normalization | `loudnorm=I=-20:TP=-2:LRA=7` | `normalize` |

4. **VAD map** (`_voice_activity_map`, opt-in) — 20 ms frames, RMS against an adaptive
   threshold (2 % of peak, floor 0.005), runs shorter than ~50 ms dropped. Emits
   `(start_s, end_s, sample_start, sample_end, offset_s)` spans.
5. **Diagnostics** — `_read_wav` computes RMS, peak, clipping fraction and silence
   fraction for both Arm A and the DSP output, and the deltas between them are stored in
   the job's `timings["dsp"]["diagnostics"]`. This is what makes the DSP effect auditable
   per job instead of assumed.

The worker uploads the DSP output to `users/{owner}/{lecture}/dsp.wav` and attaches a
15-minute signed URL to the job (`GET /api/dsp/{owner_id}/{lecture_id}/url`) so the
frontend can play back exactly what the ASR heard.

> When `PROCESSING_MODE != "real"`, `_run_media` skips ffmpeg altogether: it copies the
> source to a `dsp_`-prefixed temp file and reports zeroed stage runtimes.
> `docker-compose.yml` ships with `PROCESSING_MODE: mock`, so **DSP is off unless you
> change it.**

### 3.2 Classical enhancement — `dsp.py` (scipy, no learned model)

This is the heavier, research-grade enhancer used by `POST /api/transcriptions`
(`ENHANCE_AUDIO=true`, or `enhance=true` in the form) and by evaluation Arm C.
Audio is decoded to mono float32 @ 16 kHz via faster-whisper's PyAV decoder, then:

1. **Pre-processing** — mean (DC) removal, then a 4th-order Butterworth high-pass at
   80 Hz applied with `sosfiltfilt` (zero phase).
2. **Analysis** — 512-point STFT, Hann window, hop 128 (75 % overlap, so COLA/NOLA hold
   for exact reconstruction). Long files are processed in 90 s blocks with 2 s of
   discarded context on each side, which bounds memory and lets the noise estimate
   re-adapt across a long lecture.
3. **VAD** (`detect_speech`) — band-limited 100–4000 Hz log-energy against a threshold at
   `P10 + max(6 dB, 0.3·(P90−P10))`, then binary closing (bridge gaps < ~200 ms) and
   opening (drop bursts < ~50 ms).
4. **Noise PSD** — the average of two estimates:
   - *minimum statistics*: `noise_bias ×` a 1.5 s running minimum of the smoothed power,
     which tracks slowly non-stationary noise;
   - *VAD-held*: the smoothed power of the most recent non-speech frame, held through
     speech via a running maximum over quiet-frame indices.
5. **Late-reverberation PSD** — Lebart/Habets exponential decay: energy from 50 ms earlier
   scaled by `exp(-2·δ·τ)` with `δ = 3·ln10 / RT60`, weighted by `DSP_REVERB_WEIGHT`
   (0 ⇒ denoise only).
6. **Gain** — decision-directed (Ephraim–Malah) a-priori SNR with `α = 0.98`, Wiener gain
   `ξ/(1+ξ)`, floored at `DSP_FLOOR_DB` so attenuation is bounded and musical noise is
   limited. The real gain is applied to the complex STFT — the noisy phase is kept.
7. **Reconstruction** — inverse STFT with overlap-add, truncated/padded to the input length.
8. **Loudness** — RMS over active frames normalized to −20 dBFS (gain capped at ×100 for
   distant-mic recordings), then peak-limited to 0.99.

`spectral_subtract()` is the lighter alternative (`DSP_METHOD=spectral_subtraction`):
median-across-time noise PSD, gain `max(1 − N/P, 0)`, no VAD and no dereverberation.

`strip_silence()` removes non-speech regions and returns an **offset map** of
`(orig_start_s, orig_end_s, stripped_start_s)` tuples. This matters because the audio sent
to the ASR provider is shorter than the recording, so every returned timestamp must be
mapped back to the original timeline (`asr.py::_map_timestamp`) before it is stored.

`DspReport` is attached to the result: whether DSP applied, wall-clock seconds, duration,
VAD speech ratio, and a scale-free SNR proxy (`P90 − P10` of frame dB) measured before and
after — there is no clean reference for a real lecture, so an absolute SNR is unavailable.

---

## 4. ASR stage

`asr.py::transcribe_file` is the single entry point. It branches on `ASR_PROVIDER`.

### 4.1 Local — `faster-whisper` (pretrained; no training happens here)

The model is loaded once per process behind a lock (`get_model`) and cached in
`MODEL_CACHE_DIR`. `model.transcribe` is called with:

- `language=None` when `WHISPER_LANGUAGE` is empty/`auto` — required for the
  Filipino/English code-switching this project targets
- `beam_size=5`
- `vad_filter=True`, `min_silence_duration_ms=500` — skips silence and suppresses
  hallucinated text in quiet stretches
- `condition_on_previous_text=False` — avoids repetition loops on hour-long lectures
- `initial_prompt` = the comma-joined glossary, when one is supplied

A returned segment is kept only if it has text and `no_speech_prob ≤ 0.8`. Confidence is
`exp(avg_logprob)` clamped to `[0, 1]`. Progress is reported as `end / duration`, offset
by 0.1 when the DSP stage ran first.

### 4.2 Hosted — Groq Whisper (`ASR_PROVIDER=groq`)

Chosen for CPU-only deployments where local Whisper is too slow. Flow:

1. Decode to PCM-16 WAV (Groq needs standard PCM).
2. Optionally run `dsp.enhance`. DSP errors are recorded in `dsp_info` and transcription
   continues on the unenhanced audio rather than failing the job.
3. `strip_silence` → keep the offset map.
4. Split into `CHUNK_SECONDS` (30 s) windows with `CHUNK_OVERLAP_SECONDS` (5 s) overlap,
   so the provider's per-request size limit is never hit and word boundaries are not cut.
5. `POST` each chunk to `https://api.groq.com/openai/v1/audio/transcriptions`
   (`response_format=verbose_json`, glossary passed as `prompt`).
6. **Rate limiting:** a `429` triggers exponential backoff with jitter, honouring
   `Retry-After` when present, capped at 30 s and 5 attempts; network errors retry
   separately inside `groq_asr.py`.
7. Remap every chunk-relative timestamp: chunk offset → stripped timeline → original
   timeline via `_map_timestamp`, then round to 2 dp.
8. If the API returns only a flat `text` field with no segments, one full-duration segment
   is synthesized.

Either way the result is a `Transcript(language, duration, segments[], offset_map)` whose
segments are `Segment(id, start, end, text, confidence)`. The worker writes it to
`users/{owner}/{lecture}/transcript.json` and records provider, model, language, duration
and segment count in `timings["asr"]`.

---

## 5. RAG pipeline

Everything below runs inside the `INDEXING` stage of the same worker pass, so a completed
lecture is immediately queryable.

### 5.1 Chunking — `chunker.py`

Fixed **time**-window chunking, not token-window: windows of `CHUNK_SECONDS` (30 s)
advancing by `CHUNK_SECONDS − CHUNK_OVERLAP_SECONDS` (25 s). Every segment that
*intersects* the window contributes its text, and the window keeps the list of
`segment_ids` it covers. The result is a `Chunk` carrying `chunk_id`, `lecture_id`,
`version`, `segment_ids`, `start_s`, `end_s` and `text` — so a retrieved chunk can always
be traced back to a timestamp in the audio, which is what makes citations clickable.

### 5.2 Embedding — `embedder.py`

| `EMBED_PROVIDER` | Model | Dim | Notes |
|---|---|---|---|
| `hf` (default) | `sentence-transformers/all-MiniLM-L6-v2`, loaded locally | 384 | `normalize_embeddings=True`, so L2 distance is monotone in cosine similarity |
| `openai` / `groq` | `text-embedding-ada-002` over HTTP | 1536 | requires the matching API key |
| `mock` | zero vector | 3 | tests only |

The provider and revision are written back onto each chunk (`embedding_model`,
`embedding_revision`) so an index can be invalidated when the model changes.

### 5.3 Vector store — `vector_store.py`

A `faiss.IndexFlatL2` per lecture at `{LOCAL_STORAGE_ROOT}/vectors/{lecture_id}/`:
`index.faiss` plus `metadata.json` mapping the FAISS row id → the full chunk dict. Flat L2
is exact and needs no training — appropriate at single-lecture scale (hundreds of chunks),
and the reason no IVF/HNSW tuning exists here.

If FAISS is not installed, the store degrades to in-memory metadata with a linear cosine
scan, so tests and lightweight deployments still work. Reported similarity is
`1/(1 + L2 distance)`.

The worker *also* writes the enriched chunks (text + embedding) to
`users/{owner}/{lecture}/chunks.json`, which is the fallback read path for retrieval and
notes when no index is present.

### 5.4 Retrieval — `adapters/real.py::RealRetriever`

`POST /api/lectures/{id}/retrieve` with `{question, top_k}`:

1. Verify the lecture belongs to the caller → `404 NOT_FOUND` otherwise.
2. Load the lecture's FAISS store. If unavailable, read `chunks.json` and return it directly.
3. Embed the question with the **same** embedder used for indexing (wrapped in a throwaway
   `Chunk` to satisfy the batch API).
4. `index.search(query_vec, top_k)` → map row ids back through `metadata.json` → `Chunk`
   objects, truncated to `top_k` (max 20).

### 5.5 Answer generation — `answer_generator.py`

`POST /api/lectures/{id}/answer` retrieves the top-k chunks and calls
`GroqAnswerGenerator` (`openai/gpt-oss-20b` on Groq's chat-completions endpoint,
`temperature=0.0` for reproducibility). The grounding system prompt is fixed:

> Answer using only the provided context. If the context does not contain the answer, say
> you do not know. Keep answers concise and mention which source chunk each fact came from.

Context is rendered as `[Chunk {chunk_id}] {text}` blocks so the model can cite by id.
The response is an `AnswerResponse` with `blocks[]` (each listing its `source_ids`) and
`sources[]` carrying `start_s`/`end_s`/`text` per citation — the frontend uses these to
jump to the moment in the recording.

**Fallback:** if the LLM call fails (missing key, rate limit, network), the endpoint logs a
warning and returns the concatenated retrieved passages instead of an error. The answer is
degraded but the retrieval evidence is still delivered.

### 5.6 Notes — `routers/notes.py`

`POST /api/lectures/{id}/notes` loads *all* chunks for the lecture (FAISS
`reconstruct_n`, or `chunks.json`) and asks the same Groq model for a ≤300-word summary,
returned as a single `NoteEntry` whose `supporting_segment_ids` lists every contributing
chunk.

---

## 6. Job state machine

`JobStage` (`contracts.py`) is what the frontend renders as a status pill:

```
queued → validating → extracting → preprocessing → enhancing → transcribing
       → indexing → generating_notes → completed
                 ↘ rate_limited / retrying ↗
                 ↘ failed / cancelled
```

`PipelineWorker` polls every second and claims a job with a **lease** (`claim_job`,
`LEASE_SECONDS = 600`) renewed by a heartbeat thread every 200 s — a CPU Whisper run on a
long lecture takes minutes, so a short lease would let a second worker steal the job
mid-transcription. If a heartbeat fails to renew, the worker logs the lost lease and stops
heartbeating.

On any exception the job is failed with a **stable error code and a generic message**
(`PROCESSING_FAILED`, `"Processing failed (<ExceptionType>)"`); the detail — including any
local path — stays in the server log and never reaches the client. The lecture is marked
`FAILED`, and `POST /api/lectures/{id}/retry` can re-queue it.

---

## 7. Configuration

All settings are read from the environment (and a local `.env`) by
`backend/app/config.py`; no secret is read from a committed file. `ENV=production`
combined with `PROCESSING_MODE=mock` is rejected at load time. See `.env.example` for the
full set.

**Pipeline shape**

| Variable | Default | Effect |
|---|---|---|
| `PROCESSING_MODE` | `mock` | `real` enables ffmpeg media/DSP; `mock` copies the source through |
| `ASR_PROVIDER` | `none` | `faster-whisper` (local) or `groq` (hosted) |
| `EMBED_PROVIDER` | `hf` | `hf` / `openai` / `groq` / `mock` |
| `LLM_PROVIDER` | `groq` | answer + notes generation |
| `WORKER_ENABLED` | `true` | runs `PipelineWorker` in the API process |
| `REPOSITORY_BACKEND` | `auto` | `memory`, `firestore`, or auto-detect from Firebase config |
| `LOCAL_STORAGE_ROOT` | `local_storage` | root for objects and FAISS indexes |

**DSP**

| Variable | Default | Meaning |
|---|---|---|
| `DSP_ENABLED` | `false` | enables the ffmpeg DSP stages in the lecture pipeline |
| `ENHANCE_AUDIO` (alias `ENHANCE_DEFAULT`) | `false` | enables `dsp.py` enhancement for `POST /api/transcriptions` |
| `DSP_METHOD` | `wiener` | `wiener` or `spectral_subtraction` |
| `DSP_HIGH_PASS_CUTOFF_HZ` | `80` | high-pass cutoff |
| `DSP_SPECTRAL_GATING_ENABLED` | `false` | adds the `afftdn` pass |
| `DSP_RT60` | `0.5` | assumed room reverberation time (s) |
| `DSP_REVERB_WEIGHT` | `0.0` | `0` = denoise only; `0.3–0.6` adds dereverberation |
| `DSP_FLOOR_DB` | `-15` | maximum attenuation (limits musical noise) |
| `DSP_NOISE_BIAS` | `1.5` | over-estimation factor on the minimum-statistics noise PSD |

**ASR / chunking / limits**

| Variable | Default | Notes |
|---|---|---|
| `WHISPER_MODEL` | `whisper-large-v3` | must be a valid id for the selected provider |
| `WHISPER_DEVICE` | `auto` | `cpu` / `cuda` |
| `WHISPER_COMPUTE_TYPE` | `int8` | `float16` on GPU |
| `WHISPER_LANGUAGE` | *(empty)* | empty = auto-detect (needed for code-switching) |
| `MODEL_CACHE_DIR` | `/models` | persisted as a Docker volume |
| `CHUNK_SECONDS` | `30` | ASR request window **and** RAG chunk window |
| `CHUNK_OVERLAP_SECONDS` | `5` | overlap for both |
| `MAX_UPLOAD_MB` | `512` | also enforced by `client_max_body_size` in `nginx.conf` |
| `MAX_DURATION_MINUTES` | `60` | checked against the ffprobe duration |
| `PER_USER_DAILY_JOB_LIMIT` | `5` | |
| `PER_USER_LECTURE_LIMIT` | `25` | |

---

## 8. API surface

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | liveness |
| `POST` | `/api/lectures/uploads` | reserve a lecture + signed upload URL |
| `PUT` | `/api/storage/upload/{path}?expires&signature` | signed byte upload |
| `POST` | `/api/lectures/{id}/upload-complete` | verify object, queue the job (202) |
| `GET` | `/api/lectures` · `/api/lectures/{id}` | list / status |
| `POST` | `/api/lectures/{id}/retry` | re-queue a failed job |
| `DELETE` | `/api/lectures/{id}` | soft-delete |
| `GET` | `/api/dsp/{owner_id}/{lecture_id}/url` | signed URL for the DSP-enhanced WAV |
| `GET` | `/api/storage/download-url/{path}` | signed read URL |
| `POST` | `/api/lectures/{id}/retrieve` | top-k chunk retrieval |
| `POST` | `/api/lectures/{id}/answer` | grounded RAG answer with citations |
| `POST` | `/api/lectures/{id}/notes` | lecture summary |
| `POST` | `/api/transcriptions` | one-shot transcription (multipart, optional `enhance`) |
| `GET` / `DELETE` | `/api/transcriptions/{id}` | poll / discard |

Interactive docs: `http://localhost:8000/docs`.

---

## 9. Known gaps

Documented rather than hidden, because they change how the demo should be read:

- **Auth is stubbed.** `verify_id_token` accepts any bearer token and returns
  `uid="demo_user"`. There is no per-user isolation until real Firebase verification is
  restored.
- **`docker-compose.yml` runs the backend only**, on `:8000`, with `PROCESSING_MODE=mock`
  and `REPOSITORY_BACKEND=memory`. The root `Dockerfile` builds the frontend + nginx image
  (proxying `/api/` to `backend:8000`) but compose does not reference it, and in-memory
  job state is lost on restart.
- **The `transcriber` adapter is wired to `MockTranscriber`** in `adapters/__init__.py`;
  the worker bypasses it and calls `asr.transcribe_file` directly, so real ASR works but
  the adapter indirection is dead for that stage.
- **The Groq branch of `asr.py` is fragile**: it constructs `Transcript(..., dsp=...)`
  although `Transcript` has no `dsp` field, and reads `chunk_transcript` after the chunk
  loop. Prefer `ASR_PROVIDER=faster-whisper` until that branch is cleaned up.
- The repo root still carries scratch files (`debug_*.py`, `temp_*`, `run_benchmark*.py`)
  from the evaluation runs.

---

## 10. Libraries / Dependencies

<!-- AUTO-DEP-TABLES START -->
*This section is generated automatically from `frontend/package.json`, `backend/requirements.txt`, and `eval/requirements.txt` by the helper script `scripts/update_deps_readme.py`.*
<!-- AUTO-DEP-TABLES END -->

---

## 11. How to run

Docker (backend only, as compose is configured today):

```sh
docker compose up --build -d          # FastAPI on http://localhost:8000
docker compose down
```

To exercise the real pipeline, set `PROCESSING_MODE: real` in `docker-compose.yml` (the
backend image already bundles ffmpeg) and provide `GROQ_API_KEY` / `ASR_PROVIDER`.
Whisper weights land in the `model-cache` volume (`/models`) so they are downloaded once.

Local development:

```powershell
# backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# frontend (separate terminal) — Vite proxies /api/ to :8000
cd frontend
npm ci
npm run dev
```

Tests:

```sh
cd backend && pip install -r requirements-dev.txt && pytest   # stubbed model, no download
cd frontend && npm test
```

To expose a local instance for a remote demo: `ngrok http 8000` (backend) or
`ngrok http 8080` (frontend container).

---

## 12. Evaluation

The DSP/ASR evaluation lives in `eval/` and compares three **arms** (`eval/arms.py`) on
the same inputs:

| Arm | Audio under test |
|---|---|
| **A** | `extract_arm_a` only — 16 kHz mono, `loudnorm` (baseline) |
| **B** | Arm A + the `media.py` ffmpeg DSP stages (`bypass=False`) |
| **C** | Arm A + the `dsp.py` classical Wiener enhancer |

`eval/harness/mixer.py::NoiseMixer` builds the noisy test set: it loads a DEMAND
environment from `eval/manifests/noise_bank.json` (resampled to 16 kHz, mono, cached),
tiles or random-crops it to the speech length, scales it so
`noise_rms = signal_rms / 10^(SNR/20)` for the target SNR, mixes, and normalizes only if
the sum would clip.

`eval/harness/run_benchmark.py` smoke-tests the Groq ASR and LLM endpoints first, then
walks the manifest: normalize → skip clips over `MAX_DURATION_SECONDS` (30 s) →
rate-limited transcription (`GROQ_RPM`, default 20 → ~3 s between calls) → WER and
accuracy → detailed and summary CSVs under `eval/reports/`.

`eval/model_wrapper.py::ASRModelWrapper` wraps Groq Whisper for the harness, dropping
silence with `librosa.effects.split` and splitting anything over 60 s.

Metrics: `eval/metrics.py` (WER, CER, technical-term accuracy, edit distance) and
`eval/signal_metrics.py` (SI-SDR, PESQ, STOI/ESTOI, DNSMOS). Heavy metric dependencies
(`jiwer`, `pesq`, `pystoi`, `onnxruntime`) are intentionally **not** in the backend
requirements — install them separately for the harness.

One-command run:

```sh
python eval/cli.py                 # --dry-run / --skip-report / --force-manifests
```

Results land in `eval/results/` (git-ignored). Set `EVAL_DATA_ROOT` (default `E:\Datasets`)
to point at the external corpora.

There is also an in-app comparison for a single recording:

```sh
docker compose exec backend python -m app.evaluate \
  --audio /samples/lecture.m4a --reference /samples/lecture.txt \
  --terms /samples/terms.txt --out /samples/results
```

It runs the same model on raw / denoised / denoised+dereverberated audio, prints WER, CER,
term accuracy and runtime, and saves the enhanced WAVs so you can listen to them.

**Measure it, do not assume it helps.** Synthetic-signal findings from `tests/`: denoising
gains roughly **+7 dB SNR** at 0–20 dB input SNR, while dereverberation cuts the reverb
tail by up to ~6 dB but distorts clean speech — which is why `DSP_REVERB_WEIGHT` defaults
to `0`.

---

## 13. Datasets

- **M3AV** — multimodal academic lecture dataset (audio-visual + transcripts). <https://jack-zc8.github.io/M3AV-dataset-page/>
- **ACL 60/60** — IWSLT 2023 multilingual evaluation talks. <https://huggingface.co/datasets/ymoslem/acl-6060>
- **Loquacious** — short, diverse English clips for robustness testing. <https://www.isca-archive.org/interspeech_2025/parcollet25_interspeech.pdf>
- **DEMAND** — environmental noise (CC BY-SA 3.0), used as the noise bank. Each environment name (`DKITCHEN`, `OOFFICE`, …) populates the `environment` column of the benchmark manifest; an explicit `envs` list makes the selection deliberate, otherwise environments are sampled at random. <https://zenodo.org/record/1227120>
- **MUSAN** — music/speech/noise corpus for noise addition. <https://www.openslr.org/17/>
>>>>>>> for-demo
