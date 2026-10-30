# LectureFlow

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
