# LectureFlow

LectureFlow is a full-stack lecture transcription and study assistant. It ingests audio/video lectures, preprocesses and optionally enhances audio, transcribes speech with Whisper, chunks/indexes transcripts for retrieval, and generates grounded Q&A/notes through an LLM. It also ships an evaluation harness for WER/CER, term accuracy, and DSP/noise-ablation experiments.

## Main functions

- **Upload and transcription**: initiate uploads, process media locally, run background transcription jobs, track progress/stage, retry/cancel.
- **Audio preprocessing / DSP**: FFmpeg-based decode/probe, high-pass filtering, spectral/Wiener enhancement, noise estimation, STFT/ISTFT enhancement, loudness normalization.
- **ASR**: faster-whisper inference with VAD filtering, segment timestamps, confidence, optional glossary prompting.
- **Retrieval/RAG**: overlap chunking, MiniLM embeddings, FAISS (or metadata fallback), top-k vector search, grounded answer generation plus DuckDuckGo grounding.
- **Notes and export**: generate lecture notes, export transcripts/notes.
- **Evaluation**: compare raw/enhanced transcription and DSP arms using WER, CER, term presence, NSHR across ACL6060, DEMAND, and M3AV data.

## Software components

- Frontend SPA: React 19 + Vite pages for recording, processing, results, recordings, search, and notes.
- FastAPI backend: routers for lectures, storage, DSP, export, notes, Q&A, health; in-process worker queue.
- Media/DSP pipeline: local FFmpeg handling and classical speech enhancement.
- ASR: faster-whisper wrapper and transcription orchestration.
- Chunking/Vector store: overlap chunking, embedding, FAISS or fallback index, Q&A retrieval.
- Evaluation harness: datasets, ablation arms, metrics, reports.
- Hosting: Docker Compose with backend, frontend/nginx, model download, local storage volumes.

## Dependencies

### Frontend (`frontend/package.json`)

| Dependency | Version | Function |
|---|---:|---|
| react | ^19.3.0 | Core UI framework |
| react-dom | ^19.3.0 | Browser DOM rendering |
| react-router-dom | ^6.28.0 | Client-side routing/layout |
| react-markdown | ^10.1.0 | Markdown rendering for notes/transcripts |
| remark-gfm | ^4.0.1 | GitHub-flavored Markdown |
| remark-math | ^6.0.0 | Math Markdown syntax |
| rehype-katex | ^7.0.1 | KaTeX transform in Markdown pipeline |
| katex | ^0.19.1 | Math typesetting |
| @uiw/react-codemirror | ^4.25.12 | Editable code/text surfaces |
| @codemirror/* | ^6.x/^0.19 | Editor state, commands, history, Markdown language |
| animejs | ^4.5.0 | UI motion/transitions |
| js-yaml | ^5.5.0 | Processing profile YAML parsing |
| lucide-react | ^0.539.0 | Icon set |
| vite (dev) | ^6.4.4 | Dev server and production build |
| typescript (dev) | ^5.6.3 | Type checking |
| tailwindcss (dev) | ^3.4.19 | Utility-first styling |
| vitest (dev) | ^3.2.7 | Frontend tests |

### Backend (`backend/requirements.txt`)

| Dependency | Version (observed where available) | Function |
|---|---:|---|
| fastapi | >=0.115,<1 (0.162.0) | API framework and dependency injection |
| uvicorn[standard] | >=0.34,<1 (0.54.0) | ASGI server/entrypoint |
| pydantic-settings | >=2.5,<3 (2.14.2) | Typed env/settings (`config.py`) |
| python-dotenv | >=1,<2 (1.2.2) | `.env` loading |
| python-multipart | >=0.0.12 | Upload parsing |
| requests | >=2.32,<3 (2.34.2) | HTTP calls for providers/search |
| httpx | >=0.27,<1 (0.28.1) | HTTP client library |
| langchain | >=0.3,<2 (1.4.7) | LLM/vector utilities |
| langchain-community | >=0.3,<1 (0.4.2) | FAISS wrappers and embedding fallbacks |
| langchain-groq | >=0.1,<1 (0.3.8) | Groq chat model client |
| langchain-ollama | >=0.2,<2 (1.1.0) | Ollama chat model client |
| langchain-huggingface | 0.3.1 installed | HuggingFace embeddings wrapper |
| sentence-transformers | >=2.2,<3 | MiniLM embeddings model |
| torch | >=2.0,<3 | Runtime for sentence-transformers/HF |
| rapidfuzz | >=3.8,<4 (3.14.6) | WER/CER/term distance metrics |
| pytest/ruff (dev) | >=8,<9 / >=0.6,<1 | Tests and linting |

### Audio / DSP

| Dependency | Version | Function |
|---|---:|---|
| FFmpeg / ffprobe (system) | OS/Docker provided | Decode/probe/filter/loudnorm DSP stage |
| av (PyAV) | >=14,<17 (16.1.0) | Audio/video decoding |
| scipy | >=1.13,<2 (1.18.1) | STFT/filter DSP transforms |
| numpy | >=1.26,<2 (2.5.4 observed) | Audio arrays and numerical DSP |
| ctranslate2 | 4.8.3 (transitive) | faster-whisper inference engine |
| onnxruntime | 1.31.0 (transitive) | ONNX runtime support |
| matplotlib | >=3.8,<4 (3.11.2) | Evaluation plots/reports |
| Custom DSP module | in-repo | Classical speech enhancement pipeline |

### ASR

| Dependency | Version | Function |
|---|---:|---|
| faster-whisper | >=1.1,<2 (1.2.1) | Whisper transcription, VAD, timestamps, confidence |
| Whisper model artifacts | Configured by `WHISPER_MODEL` | Downloaded into `MODEL_CACHE_DIR` |
| av (PyAV) | >=14,<17 | Container decoding |
| Custom ASR module (`asr.py`) | in-repo | Transcription orchestration and DSP interaction |

### Retrieval / RAG

| Dependency | Version | Function |
|---|---:|---|
| sentence-transformers / all-MiniLM-L6-v2 | >=2.2,<3 | 384-dimensional chunk embeddings |
| langchain-huggingface | 0.3.1 installed | Embedder adapter |
| FAISS / faiss-cpu | 1.15.1 observed | Vector index add/query/persist |
| langchain-community FAISS | 0.4.2 | Local FAISS load fallback |
| Groq/OpenAI embedding endpoints | API runtime | Remote embeddings for `openai`/`groq` providers |
| langchain-groq | 0.3.8 | Default answer generation model |
| langchain-ollama | 1.1.0 | Optional LLM provider |
| requests | 2.34.2 | DuckDuckGo HTML grounding search |
| Custom chunker/vector store | in-repo | Overlap chunking, indexing, top-k retrieval, QA |

### Hosting

| Platform/Dependency | Version | Function |
|---|---:|---|
| Docker / Docker Compose | Compose services | Orchestrates backend, frontend, model download |
| Python base image | python:3.12-slim | Backend/model-download containers |
| Node base image | node:22-alpine | Frontend build stage |
| nginx | nginx:alpine | Static frontend serving and `/api` proxy |
| Local filesystem storage | in-repo | Uploads, vectors, jobs, DSP artifacts |
| Remote LLM endpoints | Ollama/Groq/OpenAI | Chat/embedding providers (keys server-side) |

### Evaluation

| Dependency | Version | Function |
|---|---:|---|
| Eval harness | in-repo | WER/CER/term presence/NSHR and DSP ablation arms |
| rapidfuzz | 3.14.6 | Levenshtein edit distance metrics |
| matplotlib | 3.11.2 | Report plots/artifacts |
| scipy/numpy | 1.18.1 / 2.5.4 | DSP and audio operations during arms |
| FFmpeg / faster-whisper | system / 1.2.1 | Normalization and ASR during evaluation |
| External datasets | ACL6060, DEMAND, M3AV | Evaluation corpora under `EVAL_DATA_ROOT` |

## Run the web app

### With Docker Compose (recommended)

```powershell
cd finalproject_cpe027
copy .env.example .env
docker compose up --build
```

Then open:
- Frontend: `http://localhost:8080`
- Backend API: `http://localhost:8000`
- Health check: `http://localhost:8000/api/health`

### Local development

Backend:
```powershell
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Frontend:
```powershell
cd frontend
npm ci
npm run dev
```

Notes:
- Docker Compose uses `./storage`, `./models`, and `./hf_cache` volumes for persistence.
- Set API keys (`GROQ_API_KEY`, `OPENAI_API_KEY`, `OLLAMA_API_KEY`) in `.env` before using LLM/embeddings providers.
- Default settings are configured for CPU/local runs; optional GPU requires changing `WHISPER_DEVICE` and installing a CUDA Torch build.