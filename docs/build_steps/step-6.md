# Step 6 – Chunking, embeddings, vector index

*Status*: completed  
*Artifacts*: (will be filled after implementation)  
*Changed files*:
- `backend/app/config.py` (added embed_provider literal, chunk settings)
- `backend/app/chunker.py` (new Chunker implementation)
- `backend/app/embedder.py` (new Embedder implementation)
- `backend/app/adapters/real.py` (real adapters now delegate to Chunker/Embedder)
- `backend/app/firestore_index.json` (vector index definition)
- `backend/app/tests/test_chunker.py` (unit tests)
- `backend/app/tests/test_embedder.py` (unit tests)
- `docs/build_steps/step-6.md` (this file)
*Commands run*:
```bash
set PYTHONPATH=backend && pytest backend/app/tests/test_chunker.py -q
set PYTHONPATH=backend && pytest backend/app/tests/test_embedder.py -q
```
*Owner approvals*:
- Confirm embedding provider (mock vs OpenAI) and any associated API key.
- Approve chunk size / overlap defaults (or specify alternatives).
- Approve inclusion of `firestore_index.json` for later CI deployment.
