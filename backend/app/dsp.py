"""Classical DSP speech enhancement (no learned model): the stage that runs before ASR.

Pipeline: decode -> DC/high-pass -> 512-pt STFT (75 % overlap) -> VAD -> noise PSD
(minimum statistics  VAD-held estimate) -> late-reverberation PSD (Lebart/Habets model)
-> decision-directed Wiener gain -> inverse STFT  overlap-add -> loudness normalisation.
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
    # Diagnostic only: this is P90-P10 of frame RMS levels, not reference-based SNR.
    snr_est_before_db: float = 0.0
    snr_est_after_db: float = 0.0
    frame_level_db_percentile_spread_before_db: float = 0.0
    frame_level_db_percentile_spread_after_db: float = 0.0
    frame_level_db_spread_before_db: float = 0.0
    frame_level_db_spread_after_db: float = 0.0
    frame_level_percentile_spread_before_db: float = 0.0
    frame_level_percentile_spread_after_db: float = 0.0
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

def strip_silence(
    x: np.ndarray,
    sr: int = SR,
    padding_ms: int = 250,
    min_gap_ms: int = 500,
    vad_threshold: float | None = None,
) -> tuple[np.ndarray, list[tuple[float, float, float]]]:
    """Remove silent sections while keeping a mapping to original timestamps.

    * ``x`` – Input PCM‑16 audio (float32).
    * ``sr`` – Sample rate (default 16 kHz).
    * ``padding_ms`` – Extra padding added **before and after** each speech segment
      to avoid clipping word onsets (default 250 ms).
    * ``min_gap_ms`` – Gaps shorter than this are merged instead of being cut.
    * ``vad_threshold`` – Optional custom threshold passed to ``detect_speech``.

    Returns a tuple ``(audio_stripped, offset_map)`` where ``audio_stripped`` is the
    concatenated speech audio (with padding) and ``offset_map`` is a list of tuples
    ``(orig_start_s, orig_end_s, stripped_start_s)`` for each retained segment.
    ``orig_*`` are timestamps in the original recording, ``stripped_start_s`` is the
    start time of that segment in the stripped audio. This map enables remapping of
    ASR timestamps back to the original timeline.
    """    # Compute VAD mask (binary per frame). ``detect_speech`` expects a power
    # spectrogram; we reuse it via an intermediate STFT.
    Z = stft(x)
    P = (np.abs(Z) ** 2).astype(np.float32)
    speech_mask = detect_speech(P)

    # Convert mask from frames to sample indices.
    frame_hop = HOP
    frame_len = NFFT
    # Number of frames
    n_frames = speech_mask.shape[0]
    # Determine sample boundaries for each frame
    frame_offsets = np.arange(n_frames) * frame_hop
    # Build list of speech intervals (sample indices)
    intervals: list[tuple[int, int]] = []
    in_speech = False
    start_idx = 0
    for i, is_speech in enumerate(speech_mask):
        if is_speech and not in_speech:
            in_speech = True
            start_idx = frame_offsets[i]
        elif not is_speech and in_speech:
            in_speech = False
            end_idx = frame_offsets[i] + frame_len
            intervals.append((start_idx, end_idx))
    if in_speech:
        intervals.append((start_idx, len(x)))

    # Merge intervals separated by a gap smaller than min_gap_ms
    merged: list[tuple[int, int]] = []
    min_gap_samples = int(min_gap_ms / 1000 * sr)
    for start, end in intervals:
        if not merged:
            merged.append((start, end))
        else:
            prev_start, prev_end = merged[-1]
            if start - prev_end <= min_gap_samples:
                merged[-1] = (prev_start, end)  # extend
            else:
                merged.append((start, end))

    # Apply padding around each merged interval and build offset map
    pad_samples = int(padding_ms / 1000 * sr)
    stripped_parts: list[np.ndarray] = []
    offset_map: list[tuple[float, float, float]] = []
    current_stripped = 0.0
    for seg_start, seg_end in merged:
        # Apply padding, clipped to signal bounds
        p_start = max(0, seg_start - pad_samples)
        p_end = min(len(x), seg_end + pad_samples)
        segment = x[p_start:p_end]
        stripped_parts.append(segment)
        orig_start_s = p_start / sr
        orig_end_s = p_end / sr
        offset_map.append((orig_start_s, orig_end_s, current_stripped))
        current_stripped += (p_end - p_start) / sr

    if not stripped_parts:
        # No speech detected – return original audio unchanged and an identity map.
        return x, [(0.0, len(x) / sr, 0.0)]

    audio_stripped = np.concatenate(stripped_parts).astype(np.float32)
    return audio_stripped, offset_map
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
    x: np.ndarray, rt60: float, floor_db: float, reverb_weight: float, noise_bias: float, use_vad_held: bool = True
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
    if use_vad_held:
        N = 0.5 * (N_track + N_vad)
    else:
        N = N_track

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


def frame_level_db_percentile_spread(x: np.ndarray) -> float:
    db = _frame_db(x)
    return float(np.percentile(db, 90) - np.percentile(db, 10))


def blend_observed_audio(
    enhanced: np.ndarray, prepared_highpassed: np.ndarray, observed_weight: float
) -> np.ndarray:
    """Explicit OA blend used for the experimental hp_wiener_oa arm."""
    if not 0.0 <= float(observed_weight) <= 1.0:
        raise ValueError("observed_weight must be in [0, 1]")
    enhanced_arr = np.asarray(enhanced, dtype=np.float32).ravel()
    observed_arr = np.asarray(prepared_highpassed, dtype=np.float32).ravel()
    length = min(enhanced_arr.size, observed_arr.size)
    if length == 0:
        raise ValueError("OA blend inputs must not be empty")
    enhanced_arr = enhanced_arr[:length]
    observed_arr = observed_arr[:length]
    mixed = (1.0 - float(observed_weight)) * enhanced_arr + float(observed_weight) * observed_arr
    return mixed.astype(np.float32)


# Backwards-compatible name for the diagnostic frame-level spread.
snr_proxy = frame_level_db_percentile_spread


def highpass(x: np.ndarray, cutoff_hz: float = 80.0, sr: int = SR) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    if x.size == 0:
        return x
    filtered = x.copy()
    if cutoff_hz and cutoff_hz > 0:
        try:
            filtered = (x - float(x.mean())).astype(np.float32)
            sos = signal.butter(4, float(cutoff_hz), btype="highpass", fs=sr, output="sos")
            filtered = signal.sosfiltfilt(sos, filtered).astype(np.float32)
        except ValueError:
            filtered = x
    return filtered


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
    )  # up to 40 dB for distant-mic recordings
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
    reverb_weight: float = 0.0,
    noise_bias: float = 1.5,
    method: str = "wiener",
    use_vad_held: bool = True,
    on_progress: Callable[[float], None] | None = None,
    high_pass_enabled: bool = True,
    dereverberation_enabled: bool = True,
    spectral_enhancement_enabled: bool = True,
    output_level_adjustment_enabled: bool = True,
    dc_removal_enabled: bool = True,
) -> tuple[np.ndarray, DspReport]:
    if not dereverberation_enabled:
        reverb_weight = 0.0
    t0 = time.time()
    x = np.asarray(x, dtype=np.float32)
    report = DspReport(duration=len(x) / SR, rt60_assumed=rt60, floor_db=floor_db)
    if len(x) < NFFT * 4:
        report.applied = False
        report.error = "audio too short to enhance"
        return x, report

    if not spectral_enhancement_enabled:
        # Preserve independent stage routing: no Wiener/spectral-subtraction
        # enhancement, but still apply the shared output-level policy below.
        out = x
        if output_level_adjustment_enabled:
            out = normalize_loudness(out)
        spread_before = frame_level_db_percentile_spread(x)
        spread_after = frame_level_db_percentile_spread(out)
        report.snr_est_before_db = spread_before
        report.snr_est_after_db = spread_after
        report.frame_level_db_percentile_spread_before_db = spread_before
        report.frame_level_db_percentile_spread_after_db = spread_after
        report.frame_level_db_spread_before_db = spread_before
        report.frame_level_db_spread_after_db = spread_after
        report.frame_level_percentile_spread_before_db = spread_before
        report.frame_level_percentile_spread_after_db = spread_after
        report.seconds = time.time() - t0
        report.applied = True
        return out, report

    if method == "spectral_subtraction":
        out = spectral_subtract(x)
        if output_level_adjustment_enabled:
            out = normalize_loudness(out)
        spread_before = frame_level_db_percentile_spread(x)
        spread_after = frame_level_db_percentile_spread(out)
        report.snr_est_before_db = spread_before
        report.snr_est_after_db = spread_after
        report.frame_level_db_percentile_spread_before_db = spread_before
        report.frame_level_db_percentile_spread_after_db = spread_after
        report.frame_level_db_spread_before_db = spread_before
        report.frame_level_db_spread_after_db = spread_after
        report.frame_level_percentile_spread_before_db = spread_before
        report.frame_level_percentile_spread_after_db = spread_after
        report.seconds = time.time() - t0
        return out, report
    # Wiener method (default)
    core, ctx = CHUNK_S * SR, CONTEXT_S * SR
    out = np.empty_like(x)
    speech_frames = total_frames = 0
    starts = list(range(0, len(x), core))
    for i, s in enumerate(starts):
        a, b = max(0, s - ctx), min(len(x), s + core + ctx)
        y, speech = _enhance_block(x[a:b], rt60, floor_db, reverb_weight, noise_bias, use_vad_held)
        core_len = min(core, len(x) - s)
        out[s : s + core_len] = y[s - a : s - a + core_len]
        core_start = s - a
        core_speech = speech[core_start : core_start + core_len]
        speech_frames += int(core_speech.sum())
        total_frames += int(len(core_speech))
        if on_progress:
            on_progress((i + 1) / len(starts))

    if output_level_adjustment_enabled:
        out = normalize_loudness(out)
    spread_before = frame_level_db_percentile_spread(x)
    spread_after = frame_level_db_percentile_spread(out)
    report.speech_ratio = speech_frames / max(1, total_frames)
    report.snr_est_before_db = spread_before
    report.snr_est_after_db = spread_after
    report.frame_level_db_percentile_spread_before_db = spread_before
    report.frame_level_db_percentile_spread_after_db = spread_after
    report.frame_level_db_spread_before_db = spread_before
    report.frame_level_db_spread_after_db = spread_after
    report.frame_level_percentile_spread_before_db = spread_before
    report.frame_level_percentile_spread_after_db = spread_after
    report.seconds = time.time() - t0
    return out, report


def write_wav(path: str, x: np.ndarray) -> None:
    from scipy.io import wavfile

    wavfile.write(path, SR, (np.clip(x, -1, 1) * 32767).astype(np.int16))
