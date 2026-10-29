"""Local media and DSP preprocessing tests."""

from __future__ import annotations

import array
import math
import struct
import wave
from pathlib import Path

import pytest
from app.media import (
    DSPConfig,
    MediaProcessingError,
    PathEscapeError,
    _decoded_wav,
    _safe_storage_path,
    process_local_audio,
    process_stored_media,
)


def _write_wav(
    path: Path,
    *,
    sample_rate: int = 22050,
    channels: int = 2,
    amplitude: float = 1200,
    frequency: float = 220.0,
    duration_seconds: float = 1.0,
) -> None:
    frame_count = int(sample_rate * duration_seconds)
    values: list[int] = []
    for index in range(frame_count):
        for _ in range(channels):
            values.append(
                int(amplitude * math.sin(2 * math.pi * frequency * index / sample_rate))
            )
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(array.array("h", values).tobytes())


def test_silence_retains_zero_audio(tmp_path: Path) -> None:
    source = tmp_path / "silent.wav"
    _write_wav(source, amplitude=0, channels=1)

    result = process_local_audio(
        source,
        DSPConfig(bypass=False, vad_enabled=True, normalize=True),
        output_root=tmp_path / "out",
    )

    arm = result.diagnostics["arm_a"]
    assert arm["rms"] == 0.0
    assert arm["peak"] == 0.0
    assert result.diagnostics["voice_activity_map"] == []
    assert (tmp_path / "out").is_dir()


def test_stereo_is_standardized_to_mono_16k(tmp_path: Path) -> None:
    source = tmp_path / "stereo.wav"
    _write_wav(source, channels=2, sample_rate=22050, amplitude=300)

    result = process_local_audio(
        source, DSPConfig(bypass=True), output_root=tmp_path / "out"
    )

    assert result.diagnostics["arm_a"]["channels"] == 1
    assert result.diagnostics["arm_a"]["sample_rate"] == 16000
    assert result.diagnostics["dsp"]["sample_rate"] == 16000
    assert result.diagnostics["dsp"]["channels"] == 1


def test_bypass_copies_the_normalized_baseline(tmp_path: Path) -> None:
    source = tmp_path / "audio.wav"
    _write_wav(source, channels=1, amplitude=500, frequency=100.0)

    result = process_local_audio(
        source, DSPConfig(bypass=True), output_root=tmp_path / "out"
    )

    assert result.bypassed is True
    assert result.stage_runtimes["high_pass"] == 0.0
    assert result.stage_runtimes["normalization"] == 0.0
    assert result.stage_runtimes["dsp_total"] == 0.0
    assert Path(result.dsp_path).stat().st_size > 0


def test_high_pass_and_normalization_run_with_valid_runtimes(tmp_path: Path) -> None:
    source = tmp_path / "audio.wav"
    _write_wav(source, channels=1, amplitude=250, frequency=60.0)

    result = process_local_audio(
        source,
        DSPConfig(
            bypass=False,
            high_pass_enabled=True,
            normalize=True,
            spectral_gating_enabled=True,
        ),
        output_root=tmp_path / "out",
    )

    assert result.bypassed is False
    assert result.stage_runtimes["high_pass"] >= 0.0
    assert result.stage_runtimes["normalization"] >= 0.0
    assert result.stage_runtimes["spectral_gating"] >= 0.0
    assert result.stage_runtimes["dsp_total"] >= result.stage_runtimes["high_pass"]
    assert result.diagnostics["dsp"]["sample_rate"] == 16000


def test_voice_activity_map_produces_offset_bounds(tmp_path: Path) -> None:
    source = tmp_path / "speech.wav"
    frames = bytearray()
    for _ in range(16000 // 2):
        frames.extend(struct.pack("<h", 1000))
    for _ in range(16000 // 2):
        frames.extend(struct.pack("<h", 0))
    with wave.open(str(source), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(bytes(frames))

    result = process_local_audio(
        source,
        DSPConfig(bypass=False, vad_enabled=True, normalize=True),
        output_root=tmp_path / "out",
    )
    vad_map = result.diagnostics["voice_activity_map"]
    assert vad_map
    assert vad_map[0]["start_s"] < vad_map[0]["end_s"]
    assert vad_map[0]["offset_s"] == vad_map[0]["start_s"]
    assert vad_map[0]["duration_s"] <= result.diagnostics["arm_a"]["duration_seconds"]


def test_parser_handles_float_wav(tmp_path: Path) -> None:
    source = tmp_path / "float.wav"
    samples = (0.1, 0.25, -0.4, 0.0, 0.8)
    pcm = struct.pack("<" + "f" * len(samples), *samples)
    header = struct.pack(
        "<4sI4s4sIHH", b"RIFF", 36 + len(pcm), b"WAVE", b"fmt ", 16, 3, 1
    )
    fmt = struct.pack("<IIHH", 16000, 16000 * 4, 4, 32)
    data_header = struct.pack("<4sI", b"data", len(pcm))
    source.write_bytes(header + fmt + data_header + pcm)

    sample_rate, channels, decoded = _decoded_wav(source)
    assert sample_rate == 16000
    assert channels == 1
    assert decoded == pytest.approx(list(samples))


def test_storage_path_escape_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(PathEscapeError):
        _safe_storage_path(tmp_path, "../escape.wav")


def test_stored_media_respects_storage_root(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    source = storage_root / "audio.wav"
    storage_root.mkdir(parents=True, exist_ok=True)
    _write_wav(source, channels=1, amplitude=150, duration_seconds=0.2)
    result = process_stored_media(
        storage_root,
        "audio.wav",
        output_root=tmp_path / "out",
        config=DSPConfig(bypass=True),
        max_size_bytes=10 * 1024 * 1024,
    )
    assert result.input_path == str(source.resolve())
    assert Path(result.arm_a_path).is_file()


def test_no_audioRaises_when_probe_finds_none(tmp_path: Path) -> None:
    source = tmp_path / "empty.txt"
    source.write_text("not audio", encoding="utf-8")
    with pytest.raises(MediaProcessingError, match="Invalid data found"):
        process_local_audio(
            source, DSPConfig(bypass=True), output_root=tmp_path / "out"
        )
