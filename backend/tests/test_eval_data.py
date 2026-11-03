import json
from pathlib import Path

import numpy as np
import pytest

from app import eval_data


def test_extract_bracketed_terms_deduplicates():
    text = "uses [Hann window] and [Fourier transform]; [Hann window] again"
    assert eval_data.extract_bracketed_terms(text) == ["Hann window", "Fourier transform"]


def test_parse_acl_xml_reference(tmp_path):
    xml = tmp_path / "sample.xml"
    xml.write_text(
        """<?xml version="1.0"?>
        <mteval><doc docid="talk-1"><talkid>talk-1</talkid>
        <seg id="1">hello world</seg><seg id="2">final line</seg>
        </doc></mteval>""",
        encoding="utf-8",
    )
    refs = eval_data.parse_acl_xml_reference(xml)
    assert refs == {"talk-1": "hello world final line"}


def test_mix_noise_is_seed_deterministic():
    clean = np.ones(1000, dtype=np.float32)
    noise = np.arange(1000, dtype=np.float32) / 1000.0
    first = eval_data.mix_noise(clean, noise, 5.0, seed=123)
    second = eval_data.mix_noise(clean, noise, 5.0, seed=123)
    assert np.array_equal(first, second)
    # SNR of the mix is approximately the requested value.
    noisy = eval_data.mix_noise(clean, noise, 20.0, seed=999)
    snr = eval_data.snr_db(clean, noisy)
    assert 15.0 < snr < 25.0


def test_duration_bucket_boundaries():
    assert eval_data.duration_bucket(100.0) == "<5m"
    assert eval_data.duration_bucket(400.0) == "5-10m"
    assert eval_data.duration_bucket(900.0) == "10-20m"
    assert eval_data.duration_bucket(1500.0) == ">=20m"


def test_nshr_for_segments():
    intervals = [(1.0, 2.0), (3.0, 4.0)]
    # One segment overlaps speech; one starts in silence.
    segments = [(0.5, 0.7), (1.2, 1.4)]
    assert eval_data.nshr_for_segments(segments, intervals) == 0.5


def test_parse_m3av_annotation_reads_written_text_and_terms(tmp_path):
    clip = tmp_path / "clip"
    speech = clip / "speech"
    paper = clip / "paper"
    speech.mkdir(parents=True)
    paper.mkdir(parents=True)
    annotation = speech / "final+timestamps.json"
    annotation.write_text(
        json.dumps(
            [
                {
                    "final_written": "Hello world.",
                    "words_spoken": [{"word": "hello", "start": 0.0, "end": 0.5}],
                }
            ]
        ),
        encoding="utf-8",
    )
    paper.joinpath("paper_sentences.json").write_text(
        json.dumps(["A Neural Widget uses FooBar optimization."]), encoding="utf-8"
    )
    reference, duration, intervals, terms = eval_data.parse_m3av_annotation(annotation)
    assert reference == "Hello world."
    assert duration == 0.5
    assert intervals == [(0.0, 0.5)]
    assert "Neural" in terms or "Widget" in terms or "FooBar" in terms


def test_aggregate_records_computes_mean_and_stdev():
    records = [
        {"condition": "hp", "wer": 0.1},
        {"condition": "hp", "wer": 0.3},
    ]
    rows = eval_data.aggregate_records(records, ["condition"], ["wer"])
    assert rows[0]["count"] == 2
    assert rows[0]["wer_mean"] == pytest.approx(0.2)
    assert rows[0]["wer_std"] == pytest.approx(0.141421356)