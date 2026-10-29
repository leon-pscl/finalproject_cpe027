"""Signal‑metric utilities for Tier 1 evaluation.

Wraps heavy metric libraries (torchmetrics, pesq, pystoi, DNSMOS) while keeping the
imports lazy – they are only required when the functions are called.
"""

from typing import Tuple


def si_sdr(reference, estimate) -> float:
    """Compute SI‑SDR using torchmetrics (lazy import)."""
    from torchmetrics.audio import ScaleInvariantSignalDistortionRatio

    metric = ScaleInvariantSignalDistortionRatio()
    return float(metric(reference, estimate).item())


def pesq_score(reference, estimate, sr: int = 16000) -> float:
    """Wideband PESQ score (requires `pesq`)."""
    from pesq import pesq

    # pesq expects int16 PCM arrays
    import numpy as np

    ref_int16 = (reference * 32767).astype("int16")
    est_int16 = (estimate * 32767).astype("int16")
    return float(pesq(sr, ref_int16, est_int16, 'wb'))


def stoi_score(reference, estimate, sr: int = 16000) -> float:
    """Short‑time objective intelligibility (STOI) score."""
    from pystoi import stoi

    return float(stoi(reference, estimate, sr, extended=False))


def estoi_score(reference, estimate, sr: int = 16000) -> float:
    """Extended STOI (ESTOI) score."""
    from pystoi import stoi

    return float(stoi(reference, estimate, sr, extended=True))


def dnsmos_scores(audio, sr: int = 16000) -> Tuple[float, float, float]:
    """Return (SIG, BAK, OVTL) DNSMOS scores.

    The DNSMOS model is loaded lazily; the function returns NaN if the model is
    unavailable.
    """
    try:
        from onnxruntime import InferenceSession
        import numpy as np

        # Model files are expected under a known path; this placeholder assumes
        # they are available in the working directory or a cache location.
        session = InferenceSession("dnsmos_p835.onnx")
        # Pre‑process: mono float32, 16 kHz
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        audio = audio.astype("float32")
        # Model expects shape (1, samples)
        inp = np.expand_dims(audio, 0)
        sig, bak, ovrl = session.run(None, {"input": inp})[0]
        return float(sig), float(bak), float(ovrl)
    except Exception:
        return float("nan"), float("nan"), float("nan")
