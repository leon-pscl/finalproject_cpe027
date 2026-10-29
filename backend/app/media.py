"""Safe local media extraction and DSP preprocessing.

This module extracts a normalized Arm A baseline and applies the configured DSP
stages. Every FFmpeg command is represented as an argument list; timeouts,
subprocess failures, and path traversal are handled explicitly.
"""

from __future__ import annotations

import json
import math
import shutil
import struct
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import mkdtemp
from typing import Any

from app.config import Settings


class MediaProcessingError(RuntimeError):
    """Raised when local media processing cannot be completed safely."""


class FfmpegNotFoundError(MediaProcessingError):
    """Raised when ffmpeg or ffprobe is not available."""


class PathEscapeError(MediaProcessingError):
    """Raised when a storage-relative path escapes its root."""


@dataclass(frozen=True)
class DSPConfig:
    """Configuration carried through the media pipeline."""

    version: str = "0"
    bypass: bool = True
    high_pass_enabled: bool = True
    high_pass_cutoff_hz: float = 80.0
    spectral_gating_enabled: bool = False
    spectral_gating_strength_db: float = 25.0
    normalize: bool = True
    vad_enabled: bool = False
    vad_frame_seconds: float = 0.02
    target_sample_rate: int = 16_000
    target_channels: int = 1

    @classmethod
    def from_settings(cls, settings: Settings) -> DSPConfig:
        # Arm A normalization is always performed, even when DSP stages bypass.
        return cls(
            version=str(settings.dsp_version),
            bypass=not bool(settings.dsp_enabled),
            high_pass_enabled=True,
            high_pass_cutoff_hz=float(settings.dsp_high_pass_cutoff_hz),
            spectral_gating_enabled=bool(settings.dsp_spectral_gating_enabled),
            normalize=True,
        )


@dataclass(frozen=True)
class MediaInfo:
    """Probe metadata for an input media object."""

    path: str
    format_name: str | None
    duration_seconds: float | None
    sample_rate: int | None
    channels: int | None
    codec: str | None


@dataclass(frozen=True)
class AudioStats:
    """Diagnostics calculated from one PCM rendering."""

    path: str
    duration_seconds: float
    sample_rate: int
    channels: int
    sample_count: int
    rms: float
    peak: float
    clipping_fraction: float
    silence_fraction: float


@dataclass(frozen=True)
class ProcessedAudio:
    """Result envelope for local media processing."""

    input_path: str
    arm_a_path: str
    dsp_path: str
    bypassed: bool
    diagnostics: dict[str, Any]
    stage_runtimes: dict[str, float]
    configuration: dict[str, Any]


class LocalAudioProcessor:
    """Safe local implementation of the AudioProcessor contract."""

    def process(
        self, audio_asset: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        source = Path(
            str(
                audio_asset.get("input_path")
                or audio_asset.get("path")
                or audio_asset.get("source_path")
                or ""
            )
        )
        dsp_config = DSPConfig(
            version=str(config.get("version", DSPConfig().version)),
            bypass=bool(config.get("bypass", DSPConfig().bypass)),
            high_pass_enabled=bool(config.get("high_pass_enabled", True)),
            high_pass_cutoff_hz=float(
                config.get("high_pass_cutoff_hz", DSPConfig().high_pass_cutoff_hz)
            ),
            spectral_gating_enabled=bool(
                config.get(
                    "spectral_gating_enabled", DSPConfig().spectral_gating_enabled
                )
            ),
            spectral_gating_strength_db=float(
                config.get(
                    "spectral_gating_strength_db",
                    DSPConfig().spectral_gating_strength_db,
                )
            ),
            normalize=bool(config.get("normalize", DSPConfig().normalize)),
            vad_enabled=bool(config.get("vad_enabled", DSPConfig().vad_enabled)),
            vad_frame_seconds=float(
                config.get("vad_frame_seconds", DSPConfig().vad_frame_seconds)
            ),
            target_sample_rate=int(
                config.get("target_sample_rate", DSPConfig().target_sample_rate)
            ),
            target_channels=int(
                config.get("target_channels", DSPConfig().target_channels)
            ),
        )
        output_root = audio_asset.get("output_root")
        output_root_path = Path(str(output_root)) if output_root is not None else None
        result = process_local_audio(source, dsp_config, output_root=output_root_path)
        return {
            "audio_asset": {
                "type": "local",
                "input_path": str(source),
                "arm_a_path": result.arm_a_path,
                "dsp_path": result.dsp_path,
                "format": "audio/wav",
                "sample_format": "pcm_f32le",
                "sample_rate": dsp_config.target_sample_rate,
                "channels": dsp_config.target_channels,
            },
            "diagnostics": result.diagnostics,
            "stage_runtimes": result.stage_runtimes,
            "configuration": result.configuration,
        }


# Compatibility names for adapters and existing/local unit tests.
MediaService = LocalAudioProcessor
AudioProcessor = LocalAudioProcessor


def ffmpeg_executable(name: str = "ffmpeg") -> str:
    """Return an executable path, or raise a clear actionable error."""

    if name not in {"ffmpeg", "ffprobe"}:
        raise MediaProcessingError("only ffmpeg and ffprobe are permitted")
    executable = shutil.which(name)
    if executable is None:
        raise FfmpegNotFoundError(
            f"'{name}' was not found; install FFmpeg locally before running media processing"
        )
    return executable


def run_subprocess(
    command: list[str], timeout_seconds: int
) -> subprocess.CompletedProcess[str]:
    """Run FFmpeg/FFprobe safely using an argument list and a timeout."""

    if not command or any(not isinstance(part, str) or not part for part in command):
        raise MediaProcessingError(
            "subprocess command must be a non-empty list of strings"
        )
    if timeout_seconds <= 0:
        raise MediaProcessingError("subprocess timeout must be positive")
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise FfmpegNotFoundError(f"executable not found: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaProcessingError(
            f"command timed out after {timeout_seconds} seconds"
        ) from exc
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or "").strip()
        raise MediaProcessingError(
            f"ffmpeg/ffprobe failed: {message or 'unknown error'}"
        ) from exc


def probe_media(source: Path, timeout_seconds: int = 30) -> MediaInfo:
    """Probe media without shell expansion."""

    source = source.expanduser().resolve()
    if not source.is_file():
        raise MediaProcessingError(f"input media does not exist: {source}")

    result = run_subprocess(
        [
            ffmpeg_executable("ffprobe"),
            "-v",
            "error",
            "-show_entries",
            "stream=index,codec_name,codec_type,sample_rate,channels",
            "-show_entries",
            "format=format_name,duration",
            "-of",
            "json",
            str(source),
        ],
        timeout_seconds,
    )
    try:
        payload = json.loads(result.stdout or "{}")
    except (json.JSONDecodeError, ValueError) as exc:
        raise MediaProcessingError("ffprobe returned invalid JSON") from exc

    formats = payload.get("format") or {}
    streams = payload.get("streams") or []
    audio = next(
        (
            stream
            for stream in streams
            if stream.get("codec_type") == "audio" or stream.get("channels")
        ),
        None,
    )
    if audio is None:
        raise MediaProcessingError("no audio stream found in input media")

    duration = formats.get("duration")
    sample_rate = audio.get("sample_rate")
    return MediaInfo(
        path=str(source),
        format_name=formats.get("format_name"),
        duration_seconds=float(duration) if duration is not None else None,
        sample_rate=int(sample_rate) if sample_rate is not None else None,
        channels=int(audio["channels"]),
        codec=audio.get("codec_name"),
    )


def _duration_timeout(probe: MediaInfo, timeout_seconds: int) -> int:
    estimated = max(30, timeout_seconds)
    if probe.duration_seconds is not None and probe.duration_seconds > 0:
        estimated += int(probe.duration_seconds * 3)
    return min(max(estimated, timeout_seconds), 900)


def _decoded_wav(path: Path) -> tuple[int, int, list[float]]:
    try:
        with path.open("rb") as raw_file:
            file_header = raw_file.read(12)
            if file_header[:4] != b"RIFF" or file_header[8:12] != b"WAVE":
                raise ValueError("not a RIFF/WAVE file")

            fmt: tuple[int, int, int, int, int] | None = None
            fmt_payload: bytes | None = None
            pcm_data: bytes | None = None
            while True:
                chunk_header = raw_file.read(8)
                if len(chunk_header) == 0:
                    break
                if len(chunk_header) < 8:
                    raise ValueError("truncated WAVE file")
                chunk_id, chunk_size = struct.unpack("<4sI", chunk_header)
                chunk_payload = raw_file.read(chunk_size)
                if len(chunk_payload) < chunk_size:
                    raise ValueError("truncated WAVE chunk")
                if chunk_id == b"fmt ":
                    if len(chunk_payload) < 16:
                        raise ValueError("truncated WAVE format chunk")
                    fmt = struct.unpack("<HHIIHH", chunk_payload[:16])
                    fmt_payload = chunk_payload
                elif chunk_id == b"data" and pcm_data is None:
                    pcm_data = chunk_payload
                if chunk_size % 2:
                    raw_file.read(1)
            if fmt is None or pcm_data is None:
                raise ValueError("missing WAVE format or PCM data")
            (
                audio_format,
                channels,
                sample_rate,
                _byte_rate,
                _block_align,
                bits_per_sample,
            ) = fmt
            frame_width = 0 if channels <= 0 else (channels * bits_per_sample + 7) // 8
            if channels <= 0 or sample_rate <= 0 or frame_width <= 0:
                raise ValueError("invalid WAVE format")
            if audio_format == 0xFFFE:
                if fmt_payload is None or len(fmt_payload) < 40:
                    raise ValueError("truncated extensible WAVE format")
                subformat = struct.unpack_from("<H", fmt_payload, 24)[0]
                if subformat == 1:
                    audio_format = 1
                elif subformat == 3 and bits_per_sample == 32:
                    audio_format = 3
                else:
                    raise ValueError("unsupported extensible WAVE subformat")
            if audio_format not in {1, 3}:
                raise ValueError("unsupported WAVE format")
            if len(pcm_data) % frame_width:
                raise ValueError("truncated PCM data")

            if audio_format == 1:  # PCM
                if bits_per_sample in {8, 16, 24, 32}:
                    sample_count = len(pcm_data) // frame_width
                    samples: list[float] = []
                    for frame in range(sample_count):
                        offset = frame * frame_width
                        for channel in range(channels):
                            channel_offset = offset + (channel * bits_per_sample // 8)
                            if bits_per_sample == 8:
                                value = pcm_data[channel_offset]
                                samples.append((value - 128.0) / 128.0)
                            elif bits_per_sample == 16:
                                value = struct.unpack_from(
                                    "<h", pcm_data, channel_offset
                                )[0]
                                samples.append(value / 32767.0)
                            elif bits_per_sample == 24:
                                raw_bytes = (
                                    pcm_data[channel_offset : channel_offset + 3]
                                    + b"\x00"
                                )
                                value = struct.unpack("<i", raw_bytes)[0] >> 8
                                samples.append(value / 8388607.0)
                            else:
                                value = struct.unpack_from(
                                    "<i", pcm_data, channel_offset
                                )[0]
                                samples.append(value / 2147483648.0)
                else:
                    raise ValueError("unsupported PCM bit depth")
            elif audio_format == 3 and bits_per_sample == 32:  # IEEE float
                if len(pcm_data) % (channels * 4):
                    raise ValueError("truncated float PCM data")
                samples = [value for (value,) in struct.iter_unpack("<f", pcm_data)]
            else:
                raise ValueError(
                    "only PCM and 32-bit IEEE-float WAVE data are supported"
                )

            if not samples:
                raise MediaProcessingError("audio output is empty")
            return sample_rate, channels, samples
    except (OSError, ValueError, struct.error) as exc:
        raise MediaProcessingError(f"could not read WAV diagnostics: {exc}") from exc


def _rewrite_wav_data_with_zeros(path: Path) -> None:
    """Replace the PCM payload of a WAV file with same-length zeros."""

    with path.open("rb") as raw_file:
        file_header = raw_file.read(12)
        if file_header[:4] != b"RIFF" or file_header[8:12] != b"WAVE":
            raise MediaProcessingError("not a RIFF/WAVE file")

        parsed: list[tuple[bytes, int, bytes]] = []
        while True:
            chunk_header = raw_file.read(8)
            if len(chunk_header) == 0:
                break
            if len(chunk_header) < 8:
                raise MediaProcessingError("truncated WAVE file")
            chunk_id, chunk_size = struct.unpack("<4sI", chunk_header)
            chunk_payload = raw_file.read(chunk_size)
            if len(chunk_payload) < chunk_size:
                raise MediaProcessingError("truncated WAVE chunk")
            if chunk_id == b"data":
                parsed.append((chunk_id, chunk_size, bytes(chunk_size)))
            else:
                parsed.append((chunk_id, chunk_size, chunk_payload))
            if chunk_size % 2:
                raw_file.read(1)

    temp_path = path.with_suffix(path.suffix + ".sanitized")
    try:
        with temp_path.open("wb") as output:
            output.write(file_header)
            for chunk_id, chunk_size, payload in parsed:
                output.write(chunk_id)
                output.write(struct.pack("<I", chunk_size))
                output.write(payload)
                if chunk_size % 2:
                    output.write(b"\x00")
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


def _read_wav(path: Path) -> AudioStats:
    sample_rate, channels, samples = _decoded_wav(path)

    if samples and any(not math.isfinite(value) for value in samples):
        _rewrite_wav_data_with_zeros(path)
        sample_rate, channels, samples = _decoded_wav(path)

    peak_value = max(abs(sample) for sample in samples)
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    clipped_count = sum(1 for sample in samples if abs(sample) >= 0.999)
    silence_threshold = max(0.0025, peak_value * 0.01) if peak_value > 0 else 0.0025
    silence_count = sum(1 for sample in samples if abs(sample) <= silence_threshold)

    return AudioStats(
        path=str(path),
        duration_seconds=round(len(samples) / channels / sample_rate, 3),
        sample_rate=sample_rate,
        channels=channels,
        sample_count=len(samples),
        rms=round(rms, 4),
        peak=round(peak_value, 4),
        clipping_fraction=round(clipped_count / len(samples), 4),
        silence_fraction=round(silence_count / len(samples), 4),
    )


def _safe_temp_dir(output_root: Path | None = None) -> Path:
    if output_root is None:
        return Path(mkdtemp(prefix="lecture-media-"))
    root = output_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_storage_path(storage_root: Path, storage_path: str) -> Path:
    root = storage_root.expanduser().resolve()
    relative = Path(storage_path)
    if relative.is_absolute() or not relative.parts:
        raise PathEscapeError("storage path must be relative to the storage root")
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise PathEscapeError("storage path escapes its storage root")
    candidate = root.joinpath(*relative.parts)
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PathEscapeError("storage path escapes its storage root") from exc
    return resolved


def _voice_activity_map(
    stats: AudioStats, samples: list[float], config: DSPConfig
) -> list[dict[str, Any]]:
    if not samples or not config.vad_enabled:
        return []

    samples_per_frame = max(1, int(stats.sample_rate * config.vad_frame_seconds))
    active_threshold = max(0.005, max(abs(sample) for sample in samples) * 0.02)
    active_frames: list[tuple[int, float]] = []

    for frame_index in range(len(samples) // samples_per_frame):
        frame_start = frame_index * samples_per_frame
        frame_samples = samples[frame_start : frame_start + samples_per_frame]
        rms = math.sqrt(
            sum(sample * sample for sample in frame_samples) / len(frame_samples)
        )
        if rms >= active_threshold:
            active_frames.append((frame_index, rms))

    if not active_frames:
        return []

    minimum_frames = max(1, int(1 / max(config.vad_frame_seconds, 0.005) * 0.05))
    mapped: list[dict[str, Any]] = []
    run_start, previous = active_frames[0][0], active_frames[0][0]
    rms_values = [active_frames[0][1]]

    for frame_index, rms in active_frames[1:]:
        if frame_index == previous + 1:
            previous = frame_index
            rms_values.append(rms)
            continue
        if previous - run_start + 1 >= minimum_frames:
            start_sample = run_start * samples_per_frame
            end_sample = (previous + 1) * samples_per_frame
            mapped.append(
                {
                    "start_s": round(start_sample / stats.sample_rate, 3),
                    "end_s": round(
                        min(end_sample / stats.sample_rate, stats.duration_seconds), 3
                    ),
                    "duration_s": round(
                        (end_sample - start_sample) / stats.sample_rate, 3
                    ),
                    "sample_start": start_sample,
                    "sample_end": min(end_sample, len(samples)),
                    "offset_s": round(start_sample / stats.sample_rate, 3),
                }
            )
        run_start = frame_index
        previous = frame_index
        rms_values = [rms]

    if previous - run_start + 1 >= minimum_frames:
        start_sample = run_start * samples_per_frame
        end_sample = (previous + 1) * samples_per_frame
        mapped.append(
            {
                "start_s": round(start_sample / stats.sample_rate, 3),
                "end_s": round(
                    min(end_sample / stats.sample_rate, stats.duration_seconds), 3
                ),
                "duration_s": round((end_sample - start_sample) / stats.sample_rate, 3),
                "sample_start": start_sample,
                "sample_end": min(end_sample, len(samples)),
                "offset_s": round(start_sample / stats.sample_rate, 3),
            }
        )

    return mapped


def extract_arm_a(
    source: Path,
    output: Path,
    *,
    timeout_seconds: int = 300,
) -> MediaInfo:
    """Extract mono 16 kHz Arm A baseline with level normalization."""

    source = source.expanduser().resolve()
    if not source.is_file():
        raise MediaProcessingError(f"input media does not exist: {source}")

    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)

    command = [
        ffmpeg_executable("ffmpeg"),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-vn",
        "-sn",
        "-dn",
        "-map",
        "0:a:0",
        "-ac",
        str(DSPConfig().target_channels),
        "-ar",
        str(DSPConfig().target_sample_rate),
        "-af",
        "loudnorm=I=-20:TP=-2:LRA=7",
        "-c:a",
        "pcm_f32le",
        "-f",
        "wav",
        str(output),
    ]
    run_subprocess(command, timeout_seconds=max(30, timeout_seconds))

    arm_stats = _read_wav(output)
    if arm_stats.sample_count <= 0:
        raise MediaProcessingError("Arm A extraction produced no PCM samples")
    return probe_media(source)


def process_local_audio(
    source: Path,
    config: DSPConfig,
    output_root: Path | None = None,
    timeout_seconds: int = 300,
    max_duration_minutes: int = 240,
) -> ProcessedAudio:
    """Run local media extraction and the configured DSP stages."""

    source = source.expanduser().resolve()
    if not source.is_file():
        raise MediaProcessingError(f"input media does not exist: {source}")

    root = _safe_temp_dir(output_root)
    generated_root = output_root is None
    nonce = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    arm_a_path = root / f"arm_a_{nonce}.wav"
    dsp_path = root / f"dsp_{nonce}.wav"

    try:
        probe_started = time.monotonic()
        probe = probe_media(source)
        stage_timings: dict[str, float] = {
            "probe": round(time.monotonic() - probe_started, 4)
        }

        if (
            probe.duration_seconds is not None
            and probe.duration_seconds > max_duration_minutes * 60
        ):
            raise MediaProcessingError("media duration exceeds the configured maximum")

        extract_started = time.monotonic()
        extract_arm_a(source, arm_a_path, timeout_seconds=timeout_seconds)
        stage_timings["extract_arm_a"] = round(time.monotonic() - extract_started, 4)
        arm_stats = _read_wav(arm_a_path)

        needs_vad = (not config.bypass) and config.vad_enabled
        active_filters: list[tuple[str, float, str]] = []
        if not config.bypass:
            if config.high_pass_enabled and config.high_pass_cutoff_hz > 0:
                active_filters.append(
                    (
                        "high_pass",
                        config.high_pass_cutoff_hz,
                        (
                            f"highpass=f={config.high_pass_cutoff_hz:g},areverse,"
                            f"highpass=f={config.high_pass_cutoff_hz:g},areverse"
                        ),
                    )
                )
            if config.spectral_gating_enabled:
                active_filters.append(
                    (
                        "spectral_gating",
                        config.spectral_gating_strength_db,
                        f"afftdn=nf=-{config.spectral_gating_strength_db:g}",
                    )
                )
            if config.normalize:
                active_filters.append(
                    ("normalization", 20.0, "loudnorm=I=-20:TP=-2:LRA=7")
                )

        stage_runtimes = {
            "high_pass": 0.0,
            "spectral_gating": 0.0,
            "normalization": 0.0,
            "vad": 0.0,
        }

        current = arm_a_path
        if config.bypass or not active_filters:
            shutil.copyfile(arm_a_path, dsp_path)
            stage_timings.setdefault("high_pass", 0.0)
            stage_timings.setdefault("spectral_gating", 0.0)
            stage_timings.setdefault("normalization", 0.0)
        else:
            for stage_name, _, filter_expression in active_filters:
                started = time.monotonic()
                output = root / f"dsp_{stage_name}_{nonce}.wav"
                command = [
                    ffmpeg_executable("ffmpeg"),
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(current),
                    "-af",
                    filter_expression,
                    "-ac",
                    str(config.target_channels),
                    "-ar",
                    str(config.target_sample_rate),
                    "-c:a",
                    "pcm_f32le",
                    "-f",
                    "wav",
                    str(output),
                ]
                run_subprocess(command, max(30, timeout_seconds))
                elapsed = round(time.monotonic() - started, 4)
                current = output
                stage_runtimes[stage_name] = elapsed
                stage_timings[stage_name] = round(
                    stage_timings.get(stage_name, 0.0) + elapsed, 4
                )
            if current != dsp_path:
                shutil.copyfile(current, dsp_path)

        if not dsp_path.is_file() or dsp_path.stat().st_size == 0:
            raise MediaProcessingError("DSP processing produced an empty audio file")

        dsp_stats = _read_wav(dsp_path)

        vad_map: list[dict[str, Any]] = []
        if needs_vad:
            vad_started = time.monotonic()
            _, _, arm_samples = _decoded_wav(arm_a_path)
            vad_map = _voice_activity_map(arm_stats, arm_samples, config)
            stage_runtimes["vad"] = round(time.monotonic() - vad_started, 4)

        # Maintain stable keys even when a stage did not run.
        for stage_name in ("high_pass", "spectral_gating", "normalization"):
            stage_timings.setdefault(stage_name, 0.0)
            stage_runtimes.setdefault(stage_name, 0.0)

        stage_timings["dsp_total"] = round(
            stage_timings.get("high_pass", 0.0)
            + stage_timings.get("spectral_gating", 0.0)
            + stage_timings.get("normalization", 0.0)
            + stage_runtimes.get("vad", 0.0),
            4,
        )
        stage_runtimes["dsp_total"] = stage_timings["dsp_total"]

        configuration = asdict(config)
        return ProcessedAudio(
            input_path=str(source),
            arm_a_path=str(arm_a_path),
            dsp_path=str(dsp_path),
            bypassed=config.bypass or not active_filters,
            diagnostics={
                "probe": asdict(probe),
                "arm_a": asdict(arm_stats),
                "dsp": asdict(dsp_stats),
                "voice_activity_map": vad_map,
                "peak_delta": round(dsp_stats.peak - arm_stats.peak, 4),
                "rms_delta": round(dsp_stats.rms - arm_stats.rms, 4),
                "clipping_fraction_delta": round(
                    dsp_stats.clipping_fraction - arm_stats.clipping_fraction, 4
                ),
                "silence_fraction_delta": round(
                    dsp_stats.silence_fraction - arm_stats.silence_fraction, 4
                ),
            },
            stage_runtimes={**stage_timings, **stage_runtimes},
            configuration=configuration,
        )
    except Exception:
        if generated_root:
            shutil.rmtree(root, ignore_errors=True)
        raise


class LocalMediaService:
    """Safe local implementation of media validation and extraction."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.config = DSPConfig.from_settings(settings)

    def validate_and_extract(
        self,
        *,
        owner_id: str = "local",
        lecture_id: str,
        processing_version: str = "v1",
        storage_root: Path | str | None = None,
        storage_path: str | None = None,
        source_path: str | Path | None = None,
        output_root: Path | str | None = None,
    ) -> dict[str, Any]:
        if source_path is not None:
            source = Path(source_path).expanduser().resolve()
        elif storage_root is not None and storage_path is not None:
            source = _safe_storage_path(Path(storage_root), storage_path)
        else:
            raise MediaProcessingError(
                "a source path or storage root and storage path is required"
            )

        if not source.is_file():
            raise MediaProcessingError(f"input media does not exist: {source}")
        if source.stat().st_size <= 0:
            raise MediaProcessingError("stored media is empty")
        if source.stat().st_size > self.settings.max_upload_mb * 1024 * 1024:
            raise MediaProcessingError("media is larger than the configured maximum")

        result = process_local_audio(
            source,
            self.config,
            output_root=Path(output_root) if output_root is not None else None,
            max_duration_minutes=self.settings.max_duration_minutes,
        )
        audio_asset = {
            "type": "local",
            "path": result.arm_a_path,
            "arm_a_path": result.arm_a_path,
            "dsp_path": result.dsp_path,
            "duration_s": result.diagnostics["arm_a"]["duration_seconds"],
            "format": "audio/wav",
            "sample_format": "pcm_f32le",
        }
        return {
            "lecture_id": lecture_id,
            "owner_id": owner_id,
            "processing_version": processing_version,
            "audio_asset": audio_asset,
            "diagnostics": result.diagnostics,
            "stage_runtimes": result.stage_runtimes,
            "dsp_enabled": not self.config.bypass,
            "processing_mode": "local",
        }


# Preserve the names expected by local-only adapter code and callers.
LocalMediaProcessor = LocalMediaService


def process_stored_media(
    storage_root: str | Path,
    storage_path: str,
    output_root: str | Path | None = None,
    config: DSPConfig | None = None,
    *,
    settings: Settings | None = None,
    max_size_bytes: int | None = None,
    max_duration_minutes: int = 240,
) -> ProcessedAudio:
    """Convenience entry point for media rooted in local storage."""

    root = Path(storage_root).expanduser().resolve()
    source = _safe_storage_path(root, storage_path)
    if not source.is_file():
        raise MediaProcessingError(f"stored media does not exist: {source}")
    if source.stat().st_size <= 0:
        raise MediaProcessingError("stored media is empty")
    if max_size_bytes is not None and source.stat().st_size > max_size_bytes:
        raise MediaProcessingError("stored media is larger than the configured maximum")

    effective_config = config or (
        DSPConfig.from_settings(settings) if settings is not None else DSPConfig()
    )
    return process_local_audio(
        source,
        effective_config,
        output_root=Path(output_root) if output_root is not None else None,
        max_duration_minutes=max_duration_minutes,
    )
