import soundfile as sf
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
    MAX_CHUNK_SECONDS = 60

    def __init__(self, model_path: str | None = None, device: str | None = None,
                 language: str | None = "en"):
        # model_path/device are kept for compatibility; Groq ignores them.
        settings = get_settings()
        self.api_key = getattr(settings, "groq_api_key", None)
        if not self.api_key:
            raise RuntimeError("Groq API key not configured – set GROQ_API_KEY in your environment.")
        # Whisper model identifier used by Groq (e.g., 'small', 'base')
        self.model = getattr(settings, "whisper_model", "small")
        # Pinned to English because every corpus under eval/manifests is English
        # (ACL 60/60 en dev, Loquacious/VoxPopuli en). Left to auto-detect, Whisper
        # returns a correct transcript in the wrong language on sentences that quote
        # another one, scoring ~100% WER and faking a large DSP effect.
        self.language = language
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
            language=self.language,
        )
        if not transcript.segments:
            return ""
        return " ".join(seg.text for seg in transcript.segments).strip()

    def transcribe(self, audio_path: str) -> str:
        """Transcribe `audio_path` via Groq Whisper.
        If the file exceeds Groq's payload size, it is split into <=MAX_CHUNK_SECONDS
        chunks, each sent separately, and the results are concatenated.

        Silence removal is deliberately not done here: the caller builds its arms with
        ``dsp.strip_silence`` so both arms are stripped the same way. The librosa VAD
        that used to run here gated the *return value* on its own energy split while
        still uploading the unstripped file, so a sample it judged silent scored as an
        empty hypothesis (WER 1.0) even though Whisper would have transcribed it.
        """
        audio, sr = sf.read(audio_path)
        if audio.size == 0:
            return ""
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
