"""Guards for the three bugs that made the DSP evaluation unmeasurable.

1. Metrics compared raw strings, so a perfect transcript scored ~100% WER.
2. Parquet audio was always row 0, so references did not match their audio.
3. The benchmark had no DSP arm, so nothing was actually being compared.
"""

import io

import numpy as np
import pandas as pd
import pytest
import soundfile as sf

from eval.metrics import calculate_accuracy, calculate_wer
from eval.harness.run_eval import load_audio, _safe_stem

SR = 16000

# Verbatim from eval/manifests/loq_manifest.csv and a real whisper-large-v3 reply.
REF = (
    "THESE ARE REFORMS THAT WILL DISCIPLINE AND CONSTRAIN THE EXERCISE OF POWER "
    "BY THE GOVERNMENT AND ANY OTHER ECONOMIC OR POLITICAL ACTOR FOR GENERATIONS TO COME"
)
HYP = (
    "These are reforms that will discipline and constrain the exercise of power "
    "by the government and any other economic or political actor for generations to come."
)


def test_casing_and_punctuation_do_not_count_as_errors():
    """The reported bug: datasets store ALL CAPS references, Whisper returns true case."""
    assert calculate_wer(REF, HYP) == 0.0
    assert calculate_accuracy(REF, HYP) == 1.0


def test_wer_still_counts_real_word_errors():
    hyp = HYP.replace("economic or political", "economical political")
    # "ECONOMIC OR POLITICAL" (3 words) -> "ECONOMICAL POLITICAL": 1 sub + 1 deletion.
    assert calculate_wer(REF, hyp) == pytest.approx(2 / len(REF.split()))
    assert 0.0 < calculate_accuracy(REF, hyp) < 1.0


def test_accuracy_survives_a_single_insertion():
    """The old positional zip() scored ~0 here, which is why every row read 0.0."""
    hyp = "um " + HYP
    assert calculate_accuracy(REF, hyp) > 0.9


def test_empty_hypothesis_is_a_total_miss():
    assert calculate_wer(REF, "") == 1.0
    assert calculate_accuracy(REF, "") == 0.0


def test_word_edits_is_the_wer_numerator():
    from eval.metrics import word_edits

    assert word_edits(REF, HYP) == 0
    assert word_edits("ONE TWO THREE", "one three") == 1          # deletion
    assert word_edits("ONE TWO THREE", "one two three four") == 1  # insertion
    assert word_edits("ONE TWO THREE", "") == 3
    # An empty reference cannot be scored as a ratio; the count is still the insertions.
    assert word_edits("", "one two") == 2


def test_corpus_wer_is_length_weighted_not_an_average_of_ratios():
    """A 2-word sample must not count as much as a 40-word one."""
    from eval.harness.run_benchmark import summarise_cell

    cell = pd.DataFrame({
        # Short sample: totally wrong (WER 1.0). Long sample: almost perfect (WER 0.025).
        "ref_words":   [2, 40],
        "edits_noisy": [2, 1],
        "edits_dsp":   [2, 1],
        "wer_noisy":   [1.0, 0.025],
        "wer_dsp":     [1.0, 0.025],
    })
    row = dict(zip(
        ["set", "environment", "snr", "n", "ref_words", "wer_noisy", "wer_dsp",
         "delta_wer", "delta_ci_low", "delta_ci_high", "acc_noisy", "acc_dsp"],
        summarise_cell(("s", "e", 0), cell),
    ))
    assert row["ref_words"] == 42
    assert row["wer_noisy"] == pytest.approx(3 / 42)       # pooled: 0.0714
    assert row["wer_noisy"] != pytest.approx(1.025 / 2)    # mean of ratios: 0.5125
    assert row["acc_noisy"] == pytest.approx(1 - 3 / 42)


def test_summary_cell_reports_a_paired_ci_for_a_real_improvement():
    from eval.harness.run_benchmark import summarise_cell

    cell = pd.DataFrame({
        "ref_words":   [20] * 5,
        "edits_noisy": [8, 9, 10, 8, 9],
        "edits_dsp":   [4, 5, 6, 4, 5],
        "wer_noisy":   [0.40, 0.45, 0.50, 0.40, 0.45],
        "wer_dsp":     [0.20, 0.25, 0.30, 0.20, 0.25],
    })
    row = summarise_cell(("s", "e", 0), cell)
    _, _, _, n, ref_words, wer_noisy, wer_dsp, delta, lo, hi, _, _ = row
    assert n == 5 and ref_words == 100
    assert wer_noisy == pytest.approx(0.44) and wer_dsp == pytest.approx(0.24)
    assert delta == pytest.approx(-0.20)
    assert hi < 0, "a uniformly better DSP arm must not produce a CI touching 0"


def test_bootstrap_delta_sign_matches_the_reported_convention():
    """"Negative delta = DSP helped" is the report's conclusion; the sign must not flip."""
    from eval.report import bootstrap_delta

    noisy = [0.40, 0.45, 0.50, 0.42, 0.48]
    better = [0.20, 0.25, 0.30, 0.22, 0.28]  # DSP arm wins every pair
    lo, hi = bootstrap_delta(noisy, better, n_iter=500)
    assert hi < 0, "a uniformly better DSP arm must give a negative delta CI"

    worse = [v + 0.2 for v in noisy]
    lo, hi = bootstrap_delta(noisy, worse, n_iter=500)
    assert lo > 0


def _wav_bytes(freq):
    t = np.linspace(0, 1.0, SR, endpoint=False, dtype=np.float32)
    buf = io.BytesIO()
    sf.write(buf, 0.5 * np.sin(2 * np.pi * freq * t), SR, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def test_parquet_load_selects_the_requested_utterance(tmp_path):
    """Without an id the loader returned row 0 for every reference in the shard."""
    shard = tmp_path / "dev-00000.parquet"
    pd.DataFrame({
        "ID": ["utt-a", "utt-b"],
        "wav": [{"bytes": _wav_bytes(220), "path": "a.wav"},
                {"bytes": _wav_bytes(880), "path": "b.wav"}],
        "text": ["FIRST", "SECOND"],
    }).to_parquet(shard)

    first, _ = load_audio(str(shard), "utt-a")
    second, _ = load_audio(str(shard), "utt-b")
    assert not np.allclose(first, second)
    # A missing id must fail loudly rather than silently scoring the wrong audio.
    with pytest.raises(ValueError):
        load_audio(str(shard), "utt-missing")


def test_safe_stem_strips_characters_windows_rejects():
    # Loquacious ids embed colons: 20170703-0900-PLENARY-16-en_20170703-17:34:14_15
    assert ":" not in _safe_stem("a-17:34:14_15")
    assert _safe_stem("a-17:34:14_15") == "a-17_34_14_15"


def test_build_arms_writes_a_baseline_and_an_enhanced_arm(tmp_path):
    """The DSP arm must actually differ from the baseline, or there is nothing to measure."""
    from eval.harness.run_benchmark import build_arms

    rng = np.random.default_rng(0)
    t = np.linspace(0, 3.0, 3 * SR, endpoint=False, dtype=np.float32)
    # Amplitude-modulated harmonics plus hiss: enough structure for the VAD to keep,
    # enough broadband noise for the Wiener filter to have something to remove.
    speechlike = (0.4 * (1 + np.sin(2 * np.pi * 3 * t)) / 2) * (
        np.sin(2 * np.pi * 180 * t) + 0.5 * np.sin(2 * np.pi * 540 * t)
    )
    src = tmp_path / "sample.wav"
    sf.write(src, (speechlike + 0.05 * rng.standard_normal(len(t))).astype(np.float32), SR)

    noisy_arm, dsp_arm, report = build_arms(str(src), tmp_path, "sample")

    noisy_audio, noisy_sr = sf.read(noisy_arm)
    dsp_audio, dsp_sr = sf.read(dsp_arm)
    assert noisy_sr == dsp_sr == SR
    assert noisy_audio.size > 0 and dsp_audio.size > 0
    assert report["applied"] is True
    n = min(len(noisy_audio), len(dsp_audio))
    assert not np.allclose(noisy_audio[:n], dsp_audio[:n]), "enhance() changed nothing"
