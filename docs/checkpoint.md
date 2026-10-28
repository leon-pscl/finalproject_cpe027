# Development Checkpoint

**Date:** 2026‑10‑28

## Completed milestones

- Integrated a **real‑time RAG pipeline**:
  - Added `HFEmbedder` using the `sentence‑transformers/all‑MiniLM‑L6‑v2` model (384‑dimensional vectors).
  - Implemented a disk‑backed **FAISS** vector store (`backend/app/vector_store.py`) that saves the index and a JSON metadata file for each lecture.
  - Added `OpenAIAnswerGenerator` to call `gpt‑4o‑mini` with a concise grounding prompt; includes graceful fallback when the API key is missing.
  - Updated the background worker to embed chunks and persist them to FAISS after ASR.
  - Refactored QA endpoints to retrieve via FAISS and generate answers via the new LLM wrapper.
  - Updated configuration defaults (`embed_provider="hf"`, `llm_provider="openai"`) and mock dimensions.

## Next steps

- Add tests for FAISS persistence and LLM answer generation (integration tests gated on `OPENAI_API_KEY`).
- Document deployment considerations for the FAISS index size and storage path.
- Review security around the OpenAI key handling and consider secret management.
