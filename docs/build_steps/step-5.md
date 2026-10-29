# Step 5 – ASR adapter (Groq Whisper)

*Status*: **completed**  
*Artifacts*: Groq ASR provider implementation, unit tests, documentation.  
*Changed files*:
- `backend/app/config.py` (added `groq_api_key` and expanded `asr_provider` literal)  
- `backend/app/asr.py` (delegates to Groq when `asr_provider == "groq"`)  
- `backend/app/groq_asr.py` (new module that calls Groq Whisper API)  
- `backend/tests/test_groq_asr.py` (unit tests with mocked HTTP)  
- `docs/build_steps/step-5.md` (this file)
*Commands run*:
```bash
set PYTHONPATH=backend && pytest backend/tests/test_groq_asr.py -q
```
All tests passed (2 passed).
*Owner approvals*:
- Groq API key added to `.env` (`GROQ_API_KEY=…`).  
- `ASR_PROVIDER=groq` set in `.env` to activate Groq in the pipeline.
*Next step*: Proceed to **Step 6 – Chunking, embeddings, vector index**.
