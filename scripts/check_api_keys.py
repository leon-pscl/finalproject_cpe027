

"""
Utility to verify that the external API keys (Groq ASR and Groq LLM)
are configured and functional.

It performs:
1. Groq LLM key check –
   minimal completion request. The generator uses the ``gpt-4o-mini`` model
   (hard‑coded in ``answer_generator.py``). A short prompt is sent and the
   response is printed.
2. Groq key check – if a Groq key is present it forces ``PROCESSING_MODE=real``
   and ``ASR_PROVIDER=groq`` with ``WHISPER_MODEL='whisper-large-v3'`` then calls the
   ``groq_asr.transcribe_file`` function on a tiny generated WAV file. The
   resulting transcript summary is printed.

The script is safe to run; it will only attempt network calls when the
corresponding environment variable is set. Missing keys are reported without
error.
"""
import os
import sys
import wave
import tempfile
import httpx
from pathlib import Path

# Ensure the project root is on the import path when run directly.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

# Load .env variables (python-dotenv must be installed via requirements.txt)
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

from app.config import get_settings, clear_settings_cache

from app.groq_asr import transcribe_file

def check_groq_llm_key():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[Groq LLM] No GROQ_API_KEY found – skipping Groq LLM test.")
        return
    # Force real‑mode for LLM calls.
    os.environ["PROCESSING_MODE"] = "real"
    try:
        payload = {
            "model": "openai/gpt-oss-20b",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is 2+2?"}
            ],
            "temperature": 0.0,
        }
        headers = {"Authorization": f"Bearer {api_key}"}
        resp = httpx.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        answer = data["choices"][0]["message"]["content"]
        print("[Groq LLM] Success – received answer:")
        print(answer)
    except Exception as exc:
        print(f"[Groq LLM] Failure – {exc.__class__.__name__}: {exc}")


def _create_silent_wav(duration_seconds: float = 0.5) -> Path:
    """Create a tiny silent WAV file and return its path.
    The file is small enough for quick transcription tests.
    """
    sample_rate = 16000
    n_frames = int(sample_rate * duration_seconds)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        with wave.open(tmp, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(b"\x00\x00" * n_frames)
        return Path(tmp.name)


def check_groq_key():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[Groq] No GROQ_API_KEY found – skipping Groq ASR test.")
        return
    # Force real‑mode settings for the test.
    os.environ["PROCESSING_MODE"] = "real"
    os.environ["ASR_PROVIDER"] = "groq"
    os.environ["WHISPER_MODEL"] = "whisper-large-v3"
    clear_settings_cache()
    settings = get_settings()
    if settings.processing_mode != "real" or settings.asr_provider != "groq":
        print("[Groq] Could not switch to real Groq mode – check your settings.")
        return
    print(f"[Groq] Using model: {settings.whisper_model} (expected: whisper-large-v3)")
    wav_path = _create_silent_wav()
    try:
        transcript = transcribe_file(str(wav_path))
        print("[Groq] Transcription succeeded – summary:")
        print(f"  Language: {transcript.language}, duration: {transcript.duration}s")
        print(f"  Segments: {len(transcript.segments)}")
        if transcript.segments:
            print("  First segment text:", transcript.segments[0].text)
    except Exception as exc:
        print(f"[Groq] Failure – {exc.__class__.__name__}: {exc}")
    finally:
        try:
            wav_path.unlink()
        except Exception:
            pass


def main():
    print("=== API Key Verification ===")
    check_groq_llm_key()
    print("---")
    check_groq_key()

if __name__ == "__main__":
    main()
