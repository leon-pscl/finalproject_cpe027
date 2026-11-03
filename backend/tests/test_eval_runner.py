from pathlib import Path

import pytest

from app import asr, eval_runner
from app.asr import Segment, Transcript
from app.eval_data import AclTalk, M3avClip


def _fake_processed(path: str):
    class Processed:
        dsp_path = path
        diagnostics = {"arm_a": {"duration_seconds": 1.0}, "dsp": {}}

    return Processed()


def _fake_transcript(text: str):
    return Transcript(
        language="en",
        duration=1.0,
        segments=[Segment(id="s1", start=0.0, end=1.0, text=text, confidence=1.0)],
    )


def test_run_tier1_writes_outputs(tmp_path, monkeypatch):
    audio = tmp_path / "talk.wav"
    audio.write_bytes(b"audio")
    talk = AclTalk(
        talk_id="talk-1",
        split="eval",
        audio_path=audio,
        reference="Hann window",
        terms=["Hann window"],
    )
    monkeypatch.setattr(eval_runner, "load_acl_talks", lambda split, data_root=None: [talk])
    monkeypatch.setattr(eval_runner.asr, "get_model", lambda: object())
    monkeypatch.setattr(eval_runner, "process_local_audio", lambda *a, **k: _fake_processed(str(a[0])))
    monkeypatch.setattr(eval_runner, "asr", eval_runner.asr)
    monkeypatch.setattr(eval_runner.asr, "transcribe_file", lambda *a, **k: _fake_transcript("hann window"))

    args = type("Args", (), {})()
    args.tier = "1"
    args.split = "eval"
    args.conditions = "arm_a,hp"
    args.snrs = eval_runner._parse_snrs("none")
    args.noise = "none"
    args.demand_root = None
    args.demand_env = "DKITCHEN"
    args.demand_envs = "DKITCHEN"
    args.noise_seed = 1
    args.m3av_root = None
    args.data_root = None
    args.out = str(tmp_path / "out")
    args.limit = None

    records, summary = eval_runner.run_tier1(args)
    assert len(records) == 2
    assert all(record["kter"] == pytest.approx(1.0) for record in records)
    assert (Path(args.out) / "tier1_acl_results.json").is_file()
    assert (Path(args.out) / "tier1_acl_summary.json").is_file()


def test_run_tier2_writes_outputs(tmp_path, monkeypatch):
    audio = tmp_path / "clip.mp4"
    audio.write_bytes(b"audio")
    annotation = tmp_path / "final+timestamps.json"
    annotation.write_text("[]", encoding="utf-8")
    clip = M3avClip(
        clip_id="clip-1",
        root=tmp_path,
        audio_path=audio,
        annotation_path=annotation,
        reference="hello world",
        terms=["Hello"],
        duration_seconds=10.0,
        speech_intervals=[(0.0, 1.0)],
    )
    # Replace empty reference by manual field after construction is impossible (frozen), so use M3avClip already.
    clip = M3avClip(
        clip_id="clip-1",
        root=tmp_path,
        audio_path=audio,
        annotation_path=annotation,
        reference="hello world",
        terms=["Hello"],
        duration_seconds=10.0,
        speech_intervals=[(0.0, 1.0)],
    )
    monkeypatch.setattr(eval_runner, "load_m3av_clips", lambda data_root=None: [clip])
    monkeypatch.setattr(eval_runner.asr, "get_model", lambda: object())
    monkeypatch.setattr(eval_runner, "process_local_audio", lambda *a, **k: _fake_processed(str(a[0])))
    monkeypatch.setattr(eval_runner.asr, "transcribe_file", lambda *a, **k: _fake_transcript("hello world"))

    args = type("Args", (), {})()
    args.tier = "2"
    args.conditions = "arm_a"
    args.m3av_root = str(tmp_path)
    args.data_root = None
    args.out = str(tmp_path / "out2")
    args.limit = None

    records, summary = eval_runner.run_tier2(args)
    assert len(records) == 1
    assert records[0]["duration_bucket"] == "<5m"
    assert (Path(args.out) / "tier2_m3av_results.json").is_file()
    assert (Path(args.out) / "tier2_m3av_summary.json").is_file()