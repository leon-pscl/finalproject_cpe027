import os
import hashlib
import tempfile
import tarfile
import zipfile
import subprocess
import io
import pandas as pd
import soundfile as sf
import numpy as np
import librosa
from pathlib import Path

# Global cache directory for normalized files
_CACHE_DIR = Path(tempfile.gettempdir()) / "groq_normalized"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _hash_file(path: str) -> str:
    """Return a SHA256 hash of the file's contents (or bytes column for parquet)."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _write_normalized(audio: np.ndarray, sr: int, dst_path: str) -> None:
    """Write audio to dst_path as 16‑bit PCM, mono, TARGET_SR (16000)."""
    # Ensure mono
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    # Resample if needed
    target_sr = 16000
    if sr != target_sr:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)
        sr = target_sr
    # Write as PCM_16
    sf.write(dst_path, audio, sr, subtype="PCM_16")

def _extract_first_audio_from_archive(archive_path: str) -> str:
    """Extract the first recognizable audio file from a tar/zip archive.
    Returns the path to the extracted file (still in a temp location).
    """
    audio_exts = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
    temp_dir = tempfile.mkdtemp(prefix="groq_archive_")
    # Determine archive type
    if tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path, "r:*") as tar:
            for member in tar.getmembers():
                if os.path.splitext(member.name)[1].lower() in audio_exts:
                    tar.extract(member, path=temp_dir)
                    return os.path.join(temp_dir, member.name)
    elif zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path, "r") as z:
            for name in z.namelist():
                if os.path.splitext(name)[1].lower() in audio_exts:
                    z.extract(name, path=temp_dir)
                    return os.path.join(temp_dir, name)
    raise RuntimeError(f"No audio file found inside archive {archive_path}")

def _convert_with_ffmpeg(src_path: str, dst_path: str) -> None:
    """Use ffmpeg to convert src_path to 16‑bit PCM WAV at 16 kHz mono.
    Requires ffmpeg to be available on PATH.
    """
    cmd = [
        "ffmpeg",
        "-y",  # overwrite output
        "-i", src_path,
        "-ac", "1",  # mono
        "-ar", "16000",
        "-f", "wav",
        "-acodec", "pcm_s16le",
        dst_path,
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed for {src_path}: {result.stderr.decode()}")

def normalize_audio(src_path: str) -> str:
    """Return a path to a PCM‑16, 16 kHz mono WAV suitable for Groq.
    Supports raw WAV, Parquet containers, and common archive formats.
    The function caches the result to avoid recomputation.
    """
    src_path = str(src_path)
    ext = os.path.splitext(src_path)[1].lower()
    # Determine a stable cache key
    if ext == ".parquet":
        # Load parquet to get audio bytes for hashing
        df = pd.read_parquet(src_path)
        # Find the first column that looks like audio bytes
        audio_bytes = None
        for col in ["audio", "bytes", "data", "wav"]:
            if col in df.columns:
                audio_bytes = df[col].iloc[0]
                break
        if audio_bytes is None:
            raise RuntimeError(f"No audio column found in parquet {src_path}")
        # If it's a dict (HuggingFace style) extract the bytes field
        if isinstance(audio_bytes, dict):
            audio_bytes = audio_bytes.get("bytes")
        if not isinstance(audio_bytes, (bytes, bytearray)):
            raise RuntimeError("Unsupported audio column type in parquet")
        cache_key = _hash_bytes(audio_bytes) + "_parquet"
        # Write raw bytes to a temporary WAV (ffmpeg can read from pipe; we use soundfile)
        with io.BytesIO(audio_bytes) as buf:
            audio, sr = sf.read(buf)
        # Continue to normal write
    elif ext in {".tar", ".tgz", ".gz", ".tar.gz", ".zip"}:
        # Extract first audio file and treat it like a raw audio file
        extracted_path = _extract_first_audio_from_archive(src_path)
        # Recursively call normalize_audio on the extracted file
        return normalize_audio(extracted_path)
    else:
        # Assume it's a regular audio file (wav, mp3, etc.)
        # Compute hash of the file contents
        cache_key = _hash_file(src_path) + ext
        # Load audio with soundfile (supports many formats)
        audio, sr = sf.read(src_path)

    # Determine cache filename
    cached_path = _CACHE_DIR / cache_key
    if cached_path.exists():
        return str(cached_path)

    # Write normalized audio to cache
    _write_normalized(audio, sr, str(cached_path))
    return str(cached_path)
