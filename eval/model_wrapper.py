try:
    import torch
except ImportError:
    torch = None
import soundfile as sf
import numpy as np
import os
import tempfile

# Import Groq ASR implementation from the backend package
from backend.app.config import get_settings
from backend.app.groq_asr import transcribe_file as groq_transcribe

class ASRModelWrapper:
    """Wrapper that uses Groq's Whisper API for real transcription.
    The interface matches the original dummy wrapper (only a `transcribe` method).
    """
    # Maximum chunk length (seconds) to stay within Groq's payload limits.
    MAX_CHUNK_SECONDS = 30

    def __init__(self, model_path: str | None = None, device: str | None = None):
        # model_path/device are kept for compatibility; Groq ignores them.
        settings = get_settings()
        self.api_key = getattr(settings, "groq_api_key", None)
        if not self.api_key:
            raise RuntimeError("Groq API key not configured – set GROQ_API_KEY in your environment.")
        # Whisper model identifier used by Groq (e.g., 'small', 'base')
        self.model = getattr(settings, "whisper_model", "small")
        self.settings = settings

    def _transcribe_file(self, path: str) -> str:
        """Call Groq transcribe on a single (short) audio file and return text."""
        transcript = groq_transcribe(
            path,
            on_progress=None,
            on_segment=None,
            glossary=None,
            model=self.model,
            enhance=False,
            reverb_weight=None,
            on_phase=None,
        )
        if not transcript.segments:
            return ""
        return " ".join(seg.text for seg in transcript.segments).strip()

    def transcribe(self, audio_path: str) -> str:
        """Transcribe `audio_path` via Groq Whisper.
        If the file exceeds Groq's payload size, it is split into <=MAX_CHUNK_SECONDS
        chunks, each sent separately, and the results are concatenated.
        """
        # Load audio to calculate duration (already 16 kHz mono from the harness)
        audio, sr = sf.read(audio_path)
        max_samples = int(self.MAX_CHUNK_SECONDS * sr)
        if len(audio) <= max_samples:
            # Small enough – transcribe directly
            return self._transcribe_file(audio_path)
        # Large file – split into chunks, write temporary wavs, transcribe each
        texts = []
        for start in range(0, len(audio), max_samples):
            chunk = audio[start:start + max_samples]
            fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            # Write as 16‑bit PCM (Groq expects standard PCM WAV)
            sf.write(tmp_path, chunk, sr, subtype='PCM_16')
            try:
                txt = self._transcribe_file(tmp_path)
                if txt:
                    texts.append(txt)
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        return " ".join(texts).strip()
