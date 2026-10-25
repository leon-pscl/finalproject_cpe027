# LectureFlow

LectureFlow is a lecture transcription prototype organized as separate frontend and backend applications:

- `frontend/` — React 19, Vite 6, TypeScript, and Tailwind CSS 3.4. Uploads are transcribed by the backend (real ASR). Notes, search and Q&A are still being built step by step.
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

| Variable | Default | Notes |
|---|---|---|
| `WHISPER_MODEL` | `small` | `tiny`/`base` faster, `medium`/`large-v3` more accurate (GPU advised) |
| `WHISPER_LANGUAGE` | `auto` | set `en` or `tl` to force a language |
| `WHISPER_COMPUTE_TYPE` | `int8` | use `float16` on GPU |
| `MAX_UPLOAD_MB` | `300` | |

```sh
WHISPER_MODEL=base docker compose up --build -d     # PowerShell: $env:WHISPER_MODEL="base"
```

API: `POST /api/transcriptions` (multipart `file`) -> job id; `GET /api/transcriptions/{id}` -> status, progress, segments; `DELETE` removes it. The server deletes the raw audio as soon as processing ends.

Backend tests: `cd backend && pip install -r requirements-dev.txt && pytest` (stub model; no download needed).

## DSP speech enhancement (runs before ASR)

`backend/app/dsp.py`, classical signal processing with no learned model:
decode -> mono 16 kHz -> DC removal + 80 Hz high-pass -> **512-point STFT, Hann window, 75 % overlap** -> energy/band **VAD** -> noise PSD (minimum statistics + VAD-held estimate, so it tracks non-stationary noise) -> optional late-reverberation PSD (Lebart/Habets exponential-decay model) -> decision-directed **Wiener gain** applied to the complex STFT (noisy phase kept) -> **inverse STFT + overlap-add** -> loudness normalisation (-20 dBFS RMS, peak-limited). Long lectures run in 90 s blocks.

| Variable | Default | Meaning |
|---|---|---|
| `ENHANCE_AUDIO` | `true` | enhance before ASR (`false` = raw audio) |
| `DSP_REVERB_WEIGHT` | `0.0` | `0` = denoise only; `0.3-0.6` adds dereverberation |
| `DSP_RT60` | `0.5` | assumed room reverberation time (s) |
| `DSP_FLOOR_DB` | `-15` | maximum attenuation (limits musical noise) |

**Measure it, do not assume it helps.** Put a recording and a correct transcript in `./samples/`, then:

```sh
sudo docker-compose -f compose.yaml exec backend python -m app.evaluate \
  --audio /samples/lecture.m4a --reference /samples/lecture.txt --terms /samples/terms.txt --out /samples/results
```

It runs the same Whisper model on raw / denoised / denoised+dereverberated audio and prints WER, CER, technical-term accuracy and time, and saves the enhanced WAVs so you can listen.

Synthetic-signal findings (tests/): denoising gains about +7 dB SNR at 0-20 dB input SNR; dereverberation cuts the reverb tail by up to ~6 dB but distorts clean speech, which is why it is off by default.
