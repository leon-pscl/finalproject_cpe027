import numpy as np
from dsp import enhance

def test_spectral_subtract():
    # generate 1 sec of 440Hz sine with white noise
    sr = 16000
    t = np.arange(sr) / sr
    clean = 0.5 * np.sin(2 * np.pi * 440 * t)
    noise = 0.05 * np.random.randn(sr)
    noisy = clean + noise
    out, report = enhance(noisy, method='spectral_subtraction')
    assert out.shape == noisy.shape
    # basic sanity: output RMS should be less than input RMS due to subtraction
    rms_in = np.sqrt(np.mean(noisy**2))
    rms_out = np.sqrt(np.mean(out**2))
    assert rms_out <= rms_in + 1e-6
