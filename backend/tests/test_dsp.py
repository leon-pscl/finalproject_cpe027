"""DSP checks on synthetic signals (known ground truth). They validate the maths, not ASR accuracy."""
import numpy as np
import pytest
from scipy.io import wavfile
from scipy.ndimage import binary_dilation

from app import asr, dsp, evaluate
from synth import SR, classroom_noise, mix, rir, snr, speechlike


@pytest.fixture(scope="module")
def clean():
    return speechlike(40)[0]


def highpassed(x):
    return dsp.signal.sosfiltfilt(dsp.signal.butter(4, 80, "hp", fs=SR, output="sos"), x)


def test_stft_roundtrip_is_lossless_with_512_point_hann_overlap_add():
    x = np.random.default_rng(0).standard_normal(SR * 2).astype(np.float32)
    Z = dsp.stft(x)
    assert Z.shape[0] == 257 and np.iscomplexobj(Z)  # 512-point STFT -> 257 bins, complex
    assert np.max(np.abs(dsp.istft(Z, len(x)) - x)) < 1e-4


@pytest.mark.parametrize("in_snr", [0, 5, 10, 20])
def test_denoising_never_hurts_and_helps_at_every_noise_level(clean, in_snr):
    y, _ = mix(clean, classroom_noise(len(clean)), in_snr)
    ref = highpassed(clean)
    out, rep = dsp.enhance(y.astype(np.float32), reverb_weight=0.0)
    assert snr(ref, out) - snr(ref, y) > 3.0
    assert rep.applied and len(out) == len(y)


def test_dereverb_reduces_reverb_tail():
    c, truth = speechlike(40)
    yr = np.convolve(c, rir(0.6))[:len(c)].astype(np.float32)
    tail = binary_dilation(truth, iterations=int(0.5 * SR)) & ~binary_dilation(truth, iterations=int(0.05 * SR))
    level = lambda x: 10 * np.log10((x[tail] ** 2).mean() / (x[truth] ** 2).mean())
    off, _ = dsp.enhance(yr, reverb_weight=0.0)
    on, _ = dsp.enhance(yr, reverb_weight=0.6)
    assert level(on) < level(off) - 3.0


def test_vad_flags_speech_and_not_noise():
    c, truth = speechlike(40)
    y, _ = mix(c, classroom_noise(len(c)), 15)
    ratio = dsp.enhance(y.astype(np.float32))[1].speech_ratio
    assert 0.3 < ratio < 0.7  # true ratio is ~0.56
    noise_only = dsp.enhance(classroom_noise(SR * 20).astype(np.float32))[1].speech_ratio
    assert noise_only < 0.3


def test_output_is_normalised_and_unclipped(clean):
    y, _ = mix(clean, classroom_noise(len(clean)), 10)
    out, _ = dsp.enhance((y * 0.01).astype(np.float32))  # very quiet input
    assert np.abs(out).max() <= 0.99 + 1e-6 and np.abs(out).max() > 0.2


def test_long_audio_is_processed_in_blocks_without_seams(monkeypatch, clean):
    monkeypatch.setattr(dsp, "CHUNK_S", 12)
    y, _ = mix(clean, classroom_noise(len(clean)), 10)
    out, _ = dsp.enhance(y.astype(np.float32), reverb_weight=0.0)
    ref = highpassed(clean)
    assert snr(ref, out) - snr(ref, y) > 3.0
    # no discontinuity at the 12 s block boundary
    edge = np.abs(np.diff(out[12 * SR - 3 : 12 * SR + 3])).max()
    assert edge < 5 * np.abs(np.diff(out)).mean() + 0.2


def test_too_short_audio_is_left_untouched():
    x = np.zeros(100, dtype=np.float32)
    out, rep = dsp.enhance(x)
    assert not rep.applied and rep.error and out is x or np.array_equal(out, x)


def test_transcribe_file_feeds_enhanced_audio_to_the_model_and_reports_dsp(tmp_path, clean):
    path = tmp_path / "a.wav"
    wavfile.write(path, SR, (clean * 32767).astype(np.int16))
    seen = {}

    class Stub:
        def transcribe(self, audio, **kw):
            seen["audio"] = audio
            return iter([]), type("I", (), {"language": "en", "duration": 40.0})()

    phases = []
    out = asr.transcribe_file(str(path), model=Stub(), enhance=True, on_phase=phases.append)
    assert isinstance(seen["audio"], np.ndarray) and seen["audio"].dtype == np.float32
    assert out.dsp["applied"] is True and phases == ["enhancing", "transcribing"]

    asr.transcribe_file(str(path), model=Stub(), enhance=False)
    assert seen["audio"] == str(path)  # raw path passed straight through


def test_dsp_failure_is_recorded_not_hidden():
    class Stub:
        def transcribe(self, audio, **kw):
            return iter([]), type("I", (), {"language": "en", "duration": 1.0})()

    out = asr.transcribe_file("/nonexistent.wav", model=Stub(), enhance=True)
    assert out.dsp["applied"] is False and out.dsp["error"]


def test_wer_cer_and_term_accuracy():
    ref = "The short-time Fourier transform uses a Hann window."
    assert evaluate.wer(ref, ref.upper()) == 0
    assert evaluate.wer("a b c d", "a x c") == pytest.approx(0.5)  # 1 substitution + 1 deletion over 4
    assert 0 < evaluate.cer("hello world", "hallo world") < 0.2
    acc, n = evaluate.term_accuracy(ref, "the short time fourier transform uses a hand window", ["Hann window", "Fourier transform", "wavelet"])
    assert n == 2 and acc == 0.5
