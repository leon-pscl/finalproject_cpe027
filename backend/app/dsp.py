"""Classical DSP speech enhancement (no learned model): the stage that runs before ASR.

Pipeline: decode -> DC/high-pass -> 512-pt STFT (75 % overlap) -> VAD -> noise PSD
(minimum statistics + VAD-held estimate) -> late-reverberation PSD (Lebart/Habets model)
-> decision-directed Wiener gain -> inverse STFT + overlap-add -> loudness normalisation.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass

import numpy as np
from scipy import signal
from scipy.ndimage import (
    binary_closing,
    binary_dilation,
    binary_opening,
    minimum_filter1d,
    uniform_filter1d,
)

SR = 16_000
NFFT = 512
HOP = 128  # 75 % overlap -> COLA/NOLA satisfied for a Hann window
CHUNK_S = 90  # process long lectures in 90-second blocks (bounded memory, per-block noise tracking)
CONTEXT_S = 2  # extra context either side of a block, discarded afterwards
TARGET_RMS_DB = -20.0
EPS = 1e-12


@dataclass
class DspReport:
    applied: bool = True
    seconds: float = 0.0
    duration: float = 0.0
    speech_ratio: float = 0.0  # share of frames the VAD marks as speech
    snr_est_before_db: float = (
        0.0  # P90 - P10 frame level: scale-free SNR proxy (no clean reference exists)
    )
    snr_est_after_db: float = 0.0
    rt60_assumed: float = 0.5
    floor_db: float = -15.0
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            k: (round(v, 3) if isinstance(v, float) else v)
            for k, v in asdict(self).items()
        }


# ---------------------------------------------------------------- STFT helpers
def stft(x: np.ndarray) -> np.ndarray:
    _, _, Z = signal.stft(
        x,
        fs=SR,
        window="hann",
        nperseg=NFFT,
        noverlap=NFFT - HOP,
        boundary="zeros",
        padded=True,
    )
    return Z


def istft(Z: np.ndarray, length: int) -> np.ndarray:
    _, x = signal.istft(
        Z, fs=SR, window="hann", nperseg=NFFT, noverlap=NFFT - HOP, boundary=True
    )
    x = x[:length]
    return np.pad(x, (0, length - len(x))).astype(np.float32)


def load_audio(path: str) -> np.ndarray:
    """Any container/codec -> mono float32 at 16 kHz (uses the PyAV decoder bundled with faster-whisper)."""
    from faster_whisper.audio import decode_audio

    return decode_audio(path, sampling_rate=SR)


# ---------------------------------------------------------------- VAD
def detect_speech(P: np.ndarray) -> np.ndarray:
    """Frame-level voice activity from the power spectrogram P (freq x time).

    Band-limited (100-4000 Hz) log-energy against an adaptive threshold between the noise
    floor (P10) and the speech level (P90), then closing/opening to bridge short gaps and
    drop clicks.
    """
    freqs = np.linspace(0, SR / 2, P.shape[0])
    band = (freqs >= 100) & (freqs <= 4000)
    e = 10 * np.log10(P[band].sum(axis=0) + EPS)
    lo, hi = np.percentile(e, 10), np.percentile(e, 90)
    thr = lo + max(6.0, 0.3 * (hi - lo))
    raw = e > thr
    raw = binary_closing(raw, structure=np.ones(25))  # bridge gaps < ~200 ms
    raw = binary_opening(raw, structure=np.ones(6))  # drop bursts < ~50 ms
    return raw


# ---------------------------------------------------------------- one block
def _enhance_block(
    x: np.ndarray, rt60: float, floor_db: float, reverb_weight: float, noise_bias: float
) -> tuple[np.ndarray, np.ndarray]:
    Z = stft(x)
    P = (np.abs(Z) ** 2).astype(np.float32)
    F, T = P.shape
    speech = detect_speech(P)

    # Noise PSD, estimate 1: minimum statistics (tracks non-stationary noise).
    Psm = uniform_filter1d(P, size=25, axis=1)
    win = max(3, int(1.5 * SR / HOP))
    N_track = noise_bias * minimum_filter1d(Psm, size=win, axis=1)

    # Noise PSD, estimate 2: smoothed power from the most recent non-speech frame (held through speech).
    quiet = ~binary_dilation(speech, iterations=12)
    idx = np.maximum.accumulate(np.where(quiet, np.arange(T), -1))
    N_vad = np.where(idx >= 0, Psm[:, np.clip(idx, 0, None)], N_track)
    N = 0.5 * (N_track + N_vad)

    # Late reverberation PSD: energy ~50 ms earlier, decayed by the room's RT60.
    delay_s = 0.05
    D = max(1, round(delay_s * SR / HOP))
    delta = 3 * np.log(10) / rt60
    gamma = float(np.exp(-2 * delta * delay_s))
    P9 = uniform_filter1d(P, size=9, axis=1)
    R = np.zeros_like(P)
    R[:, D:] = reverb_weight * gamma * P9[:, :-D]

    U = N + R + EPS  # total undesired power
    post = P / U  # a-posteriori SNR
    g_min = 10 ** (floor_db / 20)
    alpha = 0.98
    G = np.empty_like(P)
    g_prev = np.ones(F, dtype=np.float32)
    post_prev = post[:, 0]
    for t in range(T):  # decision-directed a-priori SNR (Ephraim-Malah)
        xi = alpha * (g_prev**2) * post_prev + (1 - alpha) * np.maximum(
            post[:, t] - 1.0, 0.0
        )
        g = np.maximum(xi / (1.0 + xi), g_min)
        G[:, t] = g
        g_prev, post_prev = g, post[:, t]

    # G is a real spectral gain applied to the complex STFT (noisy phase is kept).
    return istft(Z * G, len(x)), speech

# ---------------------------------------------------------------- simple spectral subtraction method
def spectral_subtract(x: np.ndarray) -> np.ndarray:
    """Apply a very simple spectral subtraction to audio.
    Uses median noise estimate across frames; no VAD or reverb handling.
    """
    Z = stft(x)
    P = (np.abs(Z) ** 2).astype(np.float32)
    N = np.median(P, axis=1, keepdims=True)
    G = np.maximum(1.0 - N / (P + EPS), 0.0)
    return istft(Z * G, len(x))




# ---------------------------------------------------------------- metrics / normalisation
def _frame_db(x: np.ndarray, frame: int = 320) -> np.ndarray:
    n = len(x) // frame
    if n == 0:
        return np.array([-120.0])
    f = x[: n * frame].reshape(n, frame)
    return 10 * np.log10((f**2).mean(axis=1) + EPS)


def snr_proxy(x: np.ndarray) -> float:
    db = _frame_db(x)
    return float(np.percentile(db, 90) - np.percentile(db, 10))


def normalize_loudness(x: np.ndarray, target_db: float = TARGET_RMS_DB) -> np.ndarray:
    db = _frame_db(x)
    active = db > np.median(db)
    frame = 320
    n = len(db)
    frames = x[: n * frame].reshape(n, frame)
    rms = (
        np.sqrt((frames[active] ** 2).mean())
        if active.any()
        else np.sqrt((x**2).mean() + EPS)
    )
    gain = min(
        10 ** (target_db / 20) / (rms + EPS), 100.0
    )  # up to +40 dB for distant-mic recordings
    y = x * gain
    peak = float(np.abs(y).max())
    if peak > 0.99:
        y *= 0.99 / peak
    return y.astype(np.float32)


# ---------------------------------------------------------------- public API
def enhance(
    x: np.ndarray,
    rt60: float = 0.5,
    floor_db: float = -15.0,
    reverb_weight: float = 1.0,
    noise_bias: float = 1.5,
    method: str = "wiener",
    on_progress: Callable[[float], None] | None = None,
) -> tuple[np.ndarray, DspReport]:
    t0 = time.time()
    x = np.asarray(x, dtype=np.float32)
    report = DspReport(duration=len(x) / SR, rt60_assumed=rt60, floor_db=floor_db)
    if len(x) < NFFT * 4:
        report.applied = False
        report.error = "audio too short to enhance"
        return x, report

    x = x - float(x.mean())
    sos = signal.butter(4, 80, btype="highpass", fs=SR, output="sos")
    x = signal.sosfiltfilt(sos, x).astype(np.float32)

    if method == "spectral_subtraction":
        out = spectral_subtract(x)
        out = normalize_loudness(out)
        report.snr_est_before_db = snr_proxy(x)
        report.snr_est_after_db = snr_proxy(out)
        report.seconds = time.time() - t0
        return out, report
    # Wiener method (default)
    core, ctx = CHUNK_S * SR, CONTEXT_S * SR
    out = np.empty_like(x)
    speech_frames = total_frames = 0
    starts = list(range(0, len(x), core))
    for i, s in enumerate(starts):
        a, b = max(0, s - ctx), min(len(x), s + core + ctx)
        y, speech = _enhance_block(x[a:b], rt60, floor_db, reverb_weight, noise_bias)
        out[s : min(len(x), s + core)] = y[s - a : s - a + min(core, len(x) - s)]
        speech_frames += int(speech.sum())
        total_frames += len(speech)
        if on_progress:
            on_progress((i + 1) / len(starts))

    out = normalize_loudness(out)
    report.speech_ratio = speech_frames / max(1, total_frames)
    report.snr_est_before_db = snr_proxy(x)
    report.snr_est_after_db = snr_proxy(out)
    report.seconds = time.time() - t0
    return out, report


def write_wav(path: str, x: np.ndarray) -> None:
    from scipy.io import wavfile

    wavfile.write(path, SR, (np.clip(x, -1, 1) * 32767).astype(np.int16))
