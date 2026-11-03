"""Dataset-aware ASR/DSP evaluation runner.

Tier 1 evaluates ACL6060, including seeded noise injection. Tier 2 evaluates
unmodified M3AV clips. Tiers are reported separately and never pooled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from . import asr, dsp, evaluate
from .config import EVAL_DATA_ROOT, get_settings
from .eval_data import (
    AclTalk,
    M3avClip,
    aggregate_records,
    bootstrap_ci,
    demand_noise_file,
    duration_bucket,
    extract_bracketed_terms,
    load_acl_talks,
    load_m3av_clips,
    load_noise_audio,
    m3av_root,
    mix_noise,
    noise_seed_for,
    nshr_for_segments,
    snr_improvement_db,
    write_csv,
    write_json,
)
from .media import DSPConfig, process_local_audio
def _save_waveform_png(wav_path: Path, png_path: Path) -> None:
    try:
        import numpy as np
        from scipy.io import wavfile
        from PIL import Image, ImageDraw
    except Exception:
        return
    try:
        _sr, data = wavfile.read(str(wav_path))
    except Exception:
        return
    data = np.asarray(data)
    if data.ndim > 1:
        data = data.mean(axis=1)
    data = data.astype(float)
    if data.size == 0:
        return
    max_samples = 2000
    if data.size > max_samples:
        step = data.size // max_samples
        data = data[::step]
    peak = max(abs(float(data.max())), abs(float(data.min())), 1e-9)
    data = data / peak
    width, height = 800, 200
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    mid = height // 2
    scale = (height // 2) - 5
    for i, val in enumerate(data):
        x = int(i * width / len(data))
        y = int(mid - float(val) * scale)
        draw.point((x, y), fill="black")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(png_path)


CONDITIONS = (
    "arm_a",
    "hp",
    "hp+sg",
    "hp_wiener",
    "hp_wiener_oa",
    "hp_ffmpeg",
)
CONDITION_ALIASES = {
    "a": "arm_a",
    "arm-a": "arm_a",
    "b": "hp",
    "c": "hp_wiener",
    "hp+wiener": "hp_wiener",
    "d": "hp_wiener_oa",
    "e": "hp_ffmpeg",
    "hp+ffmpeg": "hp_ffmpeg",
}

CHECKPOINT_SCHEMA_VERSION = 2
METRIC_VERSION = "1.0.0"
RESULT_SCHEMA_VERSION = 2


class CheckpointIncompatibleError(RuntimeError):
    """Raised when a checkpoint cannot be safely resumed for the current run."""
TIER1_METRICS = ["wer", "cer", "term_presence_recall", "signal_snr_improvement_db", "rtf", "seconds"]
TIER2_METRICS = ["wer", "cer", "term_presence_recall", "rtf", "seconds", "nshr"]
TIER1_CSV = [
    "tier",
    "split",
    "talk_id",
    "condition",
    "noise_type",
    "snr_db",
    "noise_seed",
    "wer",
    "cer",
    "kter",
    "term_presence_recall",
    "terms_present",
    "signal_snr_improvement_db",
    "rtf",
    "audio_duration_s",
    "seconds",
    "language",
]
TIER2_CSV = [
    "tier",
    "clip_id",
    "duration_bucket",
    "condition",
    "wer",
    "cer",
    "kter",
    "term_presence_recall",
    "terms_present",
    "nshr",
    "rtf",
    "audio_duration_s",
    "seconds",
    "language",
]
RELEVANT_DEMAND_ENVS = ("DKITCHEN", "DLIVING", "DWASHING")


def _hash_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git_state() -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}
    return {"commit": commit or None, "dirty": dirty}


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _load_checkpoint(path: Path, expected_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": CHECKPOINT_SCHEMA_VERSION, "records": [], "run_manifest": expected_manifest}
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        raise CheckpointIncompatibleError(f"incompatible checkpoint (unreadable): {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise CheckpointIncompatibleError("incompatible checkpoint (missing records list)")
    schema_version = int(payload.get("schema_version", 0))
    if schema_version != CHECKPOINT_SCHEMA_VERSION:
        raise CheckpointIncompatibleError(
            f"incompatible checkpoint schema {schema_version}; "
            "start a new run with --no-resume or remove the checkpoint"
        )
    if expected_manifest is not None and payload.get("run_manifest") != expected_manifest:
        raise CheckpointIncompatibleError("incompatible checkpoint manifest/fingerprint")
    if expected_manifest is None and payload.get("run_manifest") is not None:
        # Existing checkpoint must be validated by its own manifest; require caller to decide.
        pass
    if expected_manifest is None and payload.get("run_manifest") is not None and not isinstance(payload.get("run_manifest"), dict):
        raise CheckpointIncompatibleError("incompatible checkpoint manifest")
    return payload


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def _software_versions() -> dict[str, str]:
    versions: dict[str, str] = {"python": sys.version.split()[0]}
    for package in ("faster-whisper", "scipy", "numpy", "rapidfuzz"):
        try:
            from importlib.metadata import version

            versions[package] = version(package)
        except Exception:
            versions[package] = "unknown"
    return versions


def _run_manifest(
    *,
    tier: int,
    args: argparse.Namespace,
    settings: Any,
    talks: list[Any],
    conditions: list[str],
    noise_type: str,
    snr_values: list[Any],
    manifest_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    talk_ids = [
        getattr(talk, "talk_id", getattr(talk, "clip_id", None)) for talk in talks
    ]
    inputs = []
    for talk in talks:
        talk_id = getattr(talk, "talk_id", getattr(talk, "clip_id", None))
        reference = getattr(talk, "reference", "")
        audio_path = getattr(talk, "audio_path", None)
        inputs.append(
            {
                "id": talk_id,
                "audio_sha256": _hash_file(Path(audio_path)) if audio_path is not None else None,
                "reference_sha256": _hash_text(str(reference)),
            }
        )
    manifest = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "metric_version": METRIC_VERSION,
        "tier": tier,
        "dataset": {
            "name": "acl6060" if tier == 1 else "m3av",
            "split": getattr(args, "split", None),
            "source_ids": talk_ids,
            "limit": getattr(args, "limit", None),
        },
        "inputs": inputs,
        "noise": {
            "source": noise_type,
            "snrs": snr_values,
            "seed": getattr(args, "noise_seed", None),
            "seed_policy": "noise_seed_for(base_seed, talk_id, noise_key, snr_db)",
            "noise_file": getattr(args, "noise", None),
            "demand_envs": getattr(args, "demand_envs", None),
        },
        "model": {
            "provider": settings.asr_provider,
            "model": settings.whisper_model,
            "device": settings.whisper_device,
            "compute_type": settings.whisper_compute_type,
            "threads": settings.whisper_threads,
            "revision": "as-configured",
        },
        "language": settings.whisper_language,
        "decoding": {
            "beam_size": 5,
            "vad_filter": True,
            "vad_parameters": {"min_silence_duration_ms": 500},
            "condition_on_previous_text": False,
            "initial_prompt": None,
            "no_speech_probability_dropout": 0.8,
        },
        "preprocessing": {
            "conditions": conditions,
            "high_pass_cutoff_hz": settings.dsp_high_pass_cutoff_hz,
            "spectral_gating_enabled": settings.dsp_spectral_gating_enabled,
            "level_policy": "media extract mono 16 kHz PCM plus configured DSP stages",
        },
        "metric_version": METRIC_VERSION,
        "software": _software_versions(),
        "git": _git_state(),
    }
    if manifest_extra:
        manifest.update(manifest_extra)
    return manifest


def _tier1_record_key(record: dict[str, Any]) -> tuple[Any, ...]:
    snr = record.get("snr_db")
    return (
        record.get("split"),
        record.get("talk_id"),
        record.get("noise_type"),
        None if snr is None else float(snr),
        record.get("condition"),
    )


def _tier2_record_key(record: dict[str, Any]) -> tuple[Any, ...]:
    return (record.get("clip_id"), record.get("condition"))


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not number == number or number in (float("inf"), float("-inf")):
        return None
    return number


def _condition_config(condition: str, settings: Any, oa_weight: float = 0.3) -> DSPConfig:
    condition = CONDITION_ALIASES.get(str(condition).strip().lower(), str(condition).strip())
    if condition in {"arm_a", "A"}:
        return DSPConfig(
            bypass=True,
            high_pass_enabled=False,
            spectral_gating_enabled=False,
            normalize=True,
            target_sample_rate=16000,
            target_channels=1,
        )
    if condition in {"hp", "B"}:
        return DSPConfig(
            bypass=False,
            high_pass_enabled=True,
            high_pass_cutoff_hz=float(settings.dsp_high_pass_cutoff_hz),
            spectral_gating_enabled=False,
            normalize=True,
            target_sample_rate=16000,
            target_channels=1,
        )
    if condition in {"hp+sg", "hp+wiener", "hp_wiener", "C"}:
        return DSPConfig(
            bypass=False,
            high_pass_enabled=True,
            high_pass_cutoff_hz=float(settings.dsp_high_pass_cutoff_hz),
            spectral_gating_enabled=False,
            normalize=True,
            target_sample_rate=16000,
            target_channels=1,
        )
    if condition in {"hp_wiener_oa", "D"}:
        return DSPConfig(
            bypass=False,
            high_pass_enabled=True,
            high_pass_cutoff_hz=float(settings.dsp_high_pass_cutoff_hz),
            spectral_gating_enabled=False,
            normalize=True,
            target_sample_rate=16000,
            target_channels=1,
            # The actual OA blend still has to be implemented per arm.
            evaluation_arm="hp_wiener_oa",
            oa_weight=min(max(float(oa_weight), 0.0), 1.0),
        )
    if condition in {"hp_ffmpeg", "E"}:
        return DSPConfig(
            bypass=False,
            high_pass_enabled=True,
            high_pass_cutoff_hz=float(settings.dsp_high_pass_cutoff_hz),
            spectral_gating_enabled=True,
            spectral_gating_strength_db=25.0,
            normalize=True,
            target_sample_rate=16000,
            target_channels=1,
            evaluation_arm="hp_ffmpeg",
        )
    raise ValueError(f"unknown evaluation condition: {condition}")


def _clean_audio_path(talk: AclTalk) -> str:
    return str(talk.audio_path)


def _mixed_noise_path(
    split: str, talk_id: str, noise_key: str, snr_db: float | None, out_dir: Path
) -> Path:
    label = "clean" if snr_db is None else f"snr{snr_db:g}".replace(".", "p")
    safe_noise = re.sub(r"[^A-Za-z0-9_.-]", "_", noise_key)
    return out_dir / f"{split}_{talk_id}_{safe_noise}_{label}.wav"


def _processor_root(out_dir: Path, tier: int, talk_id: str, condition: str) -> Path:
    return out_dir / f"tier{tier}_media" / talk_id / condition


def _tier1_noise_file(args: argparse.Namespace) -> tuple[str, Path | None]:
    noise = str(args.noise).strip()
    lowered = noise.lower()
    if lowered == "none":
        return "none", None
    if lowered == "demand":
        return "demand", None
    candidate = Path(noise)
    if candidate.is_file():
        return f"wav:{candidate.name}", candidate
    raise FileNotFoundError(f"noise source is not supported or not found: {noise}")


def run_tier1(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run ACL6060 Tier 1 evaluation and return (records, summary)."""
    settings = get_settings()
    print("Loading ASR model...", flush=True)
    model = asr.get_model()
    data_root = Path(args.data_root) if args.data_root else None
    talks = load_acl_talks(args.split, data_root=data_root)
    print(f"Tier 1: {len(talks)} talks, SNRs={args.snrs}", flush=True)
    if args.limit is not None:
        talks = talks[: max(0, int(args.limit))]
    if not talks:
        raise RuntimeError("no ACL6060 talks found for the requested split")

    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    noisy_input_dir = out_dir / "tier1_noise"
    noisy_input_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_path = Path(getattr(args, "checkpoint", None) or (out_dir / "tier1_checkpoint.json")).expanduser().resolve()
    resume = bool(getattr(args, "resume", True))
    keep_media = bool(getattr(args, "keep_media", False))
    keep_asr_input = bool(getattr(args, "keep_asr_input", False))
    if not resume and checkpoint_path.exists():
        checkpoint_path.unlink(missing_ok=True)

    noise_type, noise_file = _tier1_noise_file(args)
    demand_envs = [item.strip() for item in str(args.demand_envs).split(",") if item.strip()]
    if noise_type == "demand" and not demand_envs:
        demand_envs = list(RELEVANT_DEMAND_ENVS)
    oa_weight = float(getattr(args, "oa_weight", 0.3))
    if not 0.0 <= oa_weight <= 1.0:
        raise ValueError("oa_weight must be in [0, 1]")
    if noise_type == "demand":
        # When multiple environments are requested, run them as separate records.
        demand_root = Path(args.demand_root or (Path(args.data_root or EVAL_DATA_ROOT) / "DEMAND"))
        noise_specs = [
            (f"demand:{env}", demand_noise_file(demand_root / env))
            for env in demand_envs
        ]
    else:
        noise_specs = [(noise_type, noise_file)]

    snr_values = args.snrs
    conditions = [item.strip() for item in str(args.conditions).split(",") if item.strip()]
    conditions = [CONDITION_ALIASES.get(item.lower(), item) for item in conditions]
    for condition in conditions:
        if condition not in CONDITIONS:
            raise ValueError(f"unknown condition: {condition}")

    manifest = _run_manifest(
        tier=1,
        args=args,
        settings=settings,
        talks=talks,
        conditions=conditions,
        noise_type=noise_type,
        snr_values=snr_values,
    )
    if resume:
        checkpoint = _load_checkpoint(checkpoint_path, expected_manifest=manifest)
        loaded = checkpoint.get("records", [])
        seen_keys: set[tuple[Any, ...]] = set()
        records = []
        for record in (r for r in loaded if isinstance(r, dict)):
            key = _tier1_record_key(record)
            if key not in seen_keys:
                seen_keys.add(key)
                records.append(record)
    else:
        records = []
    completed = {_tier1_record_key(record) for record in records}
    records_before = len(records)

    for talk in talks:
        clean_audio = None
        for spec_noise_type, spec_noise_file in noise_specs:
            # Lazily load noise once per specification.
            noise_audio = load_noise_audio(spec_noise_file) if spec_noise_file is not None else None
            for snr_db in snr_values:
                noisy_path = None
                is_noisy = spec_noise_file is not None and snr_db is not None
                noise_label = spec_noise_type if is_noisy else "none"
                snr_value = float(snr_db) if snr_db is not None else None
                unit_keys = {
                    _tier1_record_key(
                        {
                            "split": talk.split,
                            "talk_id": talk.talk_id,
                            "noise_type": noise_label,
                            "snr_db": snr_value,
                            "condition": condition,
                        }
                    )
                    for condition in conditions
                }
                if unit_keys.issubset(completed):
                    print(
                        f"  {talk.talk_id} | {noise_label} | SNR={snr_value} | already complete; skipping",
                        flush=True,
                    )
                    continue
                if is_noisy:
                    clean_audio = dsp.load_audio(_clean_audio_path(talk))
                    seed = noise_seed_for(
                        int(args.noise_seed),
                        talk.talk_id,
                        spec_noise_type,
                        float(snr_db),
                    )
                    noisy_audio = mix_noise(clean_audio, noise_audio, float(snr_db), seed=seed)
                    noisy_path = _mixed_noise_path(
                        talk.split, talk.talk_id, spec_noise_type, float(snr_db), noisy_input_dir
                    )
                    dsp.write_wav(str(noisy_path), noisy_audio)
                    input_path = noisy_path
                else:
                    seed = None
                    noisy_audio = None
                    noisy_path = None
                    input_path = talk.audio_path

                for condition in conditions:
                    snr_label = "clean" if snr_db is None else f"{snr_db:g} dB"
                    condition_key = _tier1_record_key(
                        {
                            "split": talk.split,
                            "talk_id": talk.talk_id,
                            "noise_type": noise_label,
                            "snr_db": snr_value,
                            "condition": condition,
                        }
                    )
                    if condition_key in completed:
                        print(
                            f"  {talk.talk_id} | {noise_label} | SNR={snr_label} | {condition} | already complete; skipping",
                            flush=True,
                        )
                        continue
                    print(
                        f"  {talk.talk_id} | {spec_noise_type} | SNR={snr_label} | {condition}",
                        flush=True,
                    )
                    config = _condition_config(condition, settings, float(getattr(args, "oa_weight", 0.3)))
                    media_root = _processor_root(out_dir, 1, talk.talk_id, condition)
                    media_root.mkdir(parents=True, exist_ok=True)
                    started = time.perf_counter()
                    processed = process_local_audio(
                        input_path,
                        config,
                        output_root=media_root,
                    )
                    audio_duration = float(
                        processed.diagnostics.get("arm_a", {}).get("duration_seconds")
                        or processed.diagnostics.get("dsp", {}).get("duration_seconds")
                        or 0.0
                    )
                    _segment_count = 0
                    _last_progress = time.perf_counter()

                    def _on_segment(segment) -> None:
                        nonlocal _segment_count, _last_progress
                        _segment_count += 1
                        now = time.perf_counter()
                        if _segment_count == 1 or _segment_count % 10 == 0 or now - _last_progress >= 5.0:
                            print(
                                f"    ASR segments: {_segment_count} "
                                f"({segment.start:.1f}-{segment.end:.1f}s)",
                                flush=True,
                            )
                            _last_progress = now

                    transcript = asr.transcribe_file(
                        processed.dsp_path,
                        model=model,
                        enhance=False,
                        on_segment=_on_segment,
                    )
                    elapsed = time.perf_counter() - started
                    text = " ".join(segment.text for segment in transcript.segments).strip()
                    segments_payload = [
                        {
                            "id": segment.id,
                            "start": segment.start,
                            "end": segment.end,
                            "text": segment.text,
                            "confidence": segment.confidence,
                        }
                        for segment in transcript.segments
                    ]
                    effective_config = getattr(processed, "configuration", None) or {}
                    input_audio_sha = _hash_file(Path(processed.dsp_path))
                    artifact_path = None
                    if keep_asr_input:
                        artifact_dir = out_dir / "artifacts" / "tier1" / talk.talk_id / condition
                        artifact_dir.mkdir(parents=True, exist_ok=True)
                        artifact_path = artifact_dir / "asr_input.wav"
                        shutil.copyfile(processed.dsp_path, artifact_path)
                    wer_value = evaluate.wer(talk.reference, text)
                    cer_value = evaluate.cer(talk.reference, text)
                    wer_edits, wer_ref_words = evaluate.wer_counts(talk.reference, text)
                    cer_edits, cer_ref_chars = evaluate.cer_counts(talk.reference, text)
                    term_recovered, term_eligible = evaluate.term_counts(talk.reference, text, talk.terms)
                    term_acc, terms_present = evaluate.term_accuracy(talk.reference, text, talk.terms)
                    term_presence_recall = None if term_eligible == 0 or term_acc != term_acc else float(term_acc)
                    rtf = elapsed / max(audio_duration, 1e-9)
                    improvement = None
                    if is_noisy:
                        enhanced_audio = dsp.load_audio(processed.dsp_path)
                        improvement = snr_improvement_db(clean_audio, noisy_audio, enhanced_audio)
                        if improvement != improvement:
                            improvement = None

                    print(
                        f"    WER {wer_value:.1%} | CER {cer_value:.1%} | "
                        f"TermPresence {0.0 if term_presence_recall is None else term_presence_recall:.1%} | RTF {rtf:.2f} | {elapsed:.1f}s",
                        flush=True,
                    )
                    records.append(
                        {
                            "tier": 1,
                            "dataset": "acl6060",
                            "split": talk.split,
                            "talk_id": talk.talk_id,
                            "audio_duration_s": audio_duration,
                            "condition": condition,
                            "noise_type": spec_noise_type if is_noisy else "none",
                            "snr_db": float(snr_db) if snr_db is not None else None,
                            "noise_seed": seed,
                            "wer": float(wer_value),
                            "cer": float(cer_value),
                            "wer_edits": int(wer_edits),
                            "wer_ref_count": int(wer_ref_words),
                            "wer_ref_words": int(wer_ref_words),
                            "cer_edits": int(cer_edits),
                            "cer_ref_count": int(cer_ref_chars),
                            "cer_ref_chars": int(cer_ref_chars),
                            "term_presence_recall": term_presence_recall,
                            "kter": term_presence_recall,
                            "term_source": "acl6060_bracketed",
                            "terms_source": "acl6060_bracketed",
                            "recovered_terms": int(term_recovered),
                            "eligible_terms": int(term_eligible),
                            "terms_recovered": int(term_recovered),
                            "terms_eligible": int(term_eligible),
                            "terms_present": int(term_eligible),
                            "reference": talk.reference,
                            "hypothesis": text,
                            "segments": segments_payload,
                            "effective_config": effective_config,
                            "input_audio_sha256": input_audio_sha,
                            "reference_sha256": _hash_text(talk.reference),
                            "hypothesis_sha256": _hash_text(text),
                            "asr_input_artifact": str(artifact_path) if artifact_path is not None else None,
                            "signal_snr_improvement_db": _safe_float(improvement),
                            "rtf": float(rtf),
                            "seconds": float(elapsed),
                            "language": transcript.language,
                            "dsp": processed.diagnostics,
                        }
                    )
                    if getattr(args, "save_waveforms", False):
                        wave_dir = out_dir / "waveforms" / "tier1" / talk.talk_id / condition
                        _save_waveform_png(Path(processed.dsp_path), wave_dir / "waveform.png")
                    completed.add(condition_key)
                    if not keep_media:
                        _atomic_write_json(
                            checkpoint_path,
                            {"schema_version": CHECKPOINT_SCHEMA_VERSION, "metric_version": METRIC_VERSION, "run_manifest": manifest, "records": records},
                        )
                        shutil.rmtree(media_root, ignore_errors=True)

                if is_noisy and noisy_path is not None and not keep_media:
                    try:
                        noisy_path.unlink(missing_ok=True)
                    except OSError:
                        pass

    group_keys = ["condition", "noise_type", "snr_db"]
    summary = aggregate_records(
        records,
        group_keys,
        TIER1_METRICS,
        bootstrap_ci_enabled=getattr(args, "bootstrap_ci", False),
        n_boot=int(getattr(args, "bootstrap_samples", 2000)),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "tier1_acl_results.json", records)
    write_json(out_dir / "tier1_acl_summary.json", summary)
    write_csv(out_dir / "tier1_acl_results.csv", records, TIER1_CSV)
    _atomic_write_json(checkpoint_path, {"schema_version": CHECKPOINT_SCHEMA_VERSION, "metric_version": METRIC_VERSION, "run_manifest": manifest, "records": records})
    return records, summary


def _m3av_duration(clip: M3avClip, audio_duration: float | None = None) -> float:
    if clip.duration_seconds and clip.duration_seconds > 0:
        return float(clip.duration_seconds)
    return float(audio_duration or 0.0)


def run_tier2(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run M3AV Tier 2 evaluation and return (records, summary)."""
    settings = get_settings()
    print("Loading ASR model...", flush=True)
    model = asr.get_model()
    clip_root = Path(args.m3av_root) if args.m3av_root else None
    clips = load_m3av_clips(data_root=clip_root or Path(args.data_root or EVAL_DATA_ROOT))
    if args.limit is not None:
        clips = clips[: max(0, int(args.limit))]
    print(f"Tier 2: {len(clips)} clips", flush=True)
    if args.limit is not None:
        clips = clips[: max(0, int(args.limit))]
    if not clips:
        raise RuntimeError("no M3AV clips found under the requested root")

    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = Path(getattr(args, "checkpoint", None) or (out_dir / "tier2_checkpoint.json")).expanduser().resolve()
    resume = bool(getattr(args, "resume", True))
    keep_media = bool(getattr(args, "keep_media", False))
    keep_asr_input = bool(getattr(args, "keep_asr_input", False))
    if not resume and checkpoint_path.exists():
        checkpoint_path.unlink(missing_ok=True)

    oa_weight = float(getattr(args, "oa_weight", 0.3))
    if not 0.0 <= oa_weight <= 1.0:
        raise ValueError("oa_weight must be in [0, 1]")
    conditions = [item.strip() for item in str(args.conditions).split(",") if item.strip()]
    conditions = [CONDITION_ALIASES.get(item.lower(), item) for item in conditions]
    for condition in conditions:
        if condition not in CONDITIONS:
            raise ValueError(f"unknown condition: {condition}")

    manifest = _run_manifest(
        tier=2,
        args=args,
        settings=settings,
        talks=clips,
        conditions=conditions,
        noise_type="none",
        snr_values=[None],
    )
    if resume:
        checkpoint = _load_checkpoint(checkpoint_path, expected_manifest=manifest)
        loaded = checkpoint.get("records", [])
        seen_keys: set[tuple[Any, ...]] = set()
        records = []
        for record in (r for r in loaded if isinstance(r, dict)):
            key = _tier2_record_key(record)
            if key not in seen_keys:
                seen_keys.add(key)
                records.append(record)
    else:
        records = []
    completed = {_tier2_record_key(record) for record in records}

    for clip in clips:
        clip_condition_keys = {
            _tier2_record_key({"clip_id": clip.clip_id, "condition": condition})
            for condition in conditions
        }
        if clip_condition_keys.issubset(completed):
            print(f"  {clip.clip_id} | already complete; skipping", flush=True)
            continue
        for condition in conditions:
            condition_key = _tier2_record_key({"clip_id": clip.clip_id, "condition": condition})
            if condition_key in completed:
                print(f"  {clip.clip_id} | {condition} | already complete; skipping", flush=True)
                continue
            print(f"  {clip.clip_id} | {condition}", flush=True)
            config = _condition_config(condition, settings, float(getattr(args, "oa_weight", 0.3)))
            media_root = out_dir / "tier2_media" / clip.clip_id / condition
            media_root.mkdir(parents=True, exist_ok=True)
            started = time.perf_counter()
            processed = process_local_audio(clip.audio_path, config, output_root=media_root)
            audio_duration = float(
                processed.diagnostics.get("arm_a", {}).get("duration_seconds")
                or processed.diagnostics.get("dsp", {}).get("duration_seconds")
                or _m3av_duration(clip)
            )
            if audio_duration <= 0:
                audio_duration = _m3av_duration(clip)
            _segment_count = 0
            _last_progress = time.perf_counter()

            def _on_segment(segment) -> None:
                nonlocal _segment_count, _last_progress
                _segment_count += 1
                now = time.perf_counter()
                if _segment_count == 1 or _segment_count % 10 == 0 or now - _last_progress >= 5.0:
                    print(
                        f"  ASR segments: {_segment_count} ({segment.start:.1f}-{segment.end:.1f}s)",
                        flush=True,
                    )
                    _last_progress = now

            transcript = asr.transcribe_file(
                processed.dsp_path,
                model=model,
                enhance=False,
                on_segment=_on_segment,
            )
            elapsed = time.perf_counter() - started
            text = " ".join(segment.text for segment in transcript.segments).strip()
            segments_payload = [
                {
                    "id": segment.id,
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                    "confidence": segment.confidence,
                }
                for segment in transcript.segments
            ]
            effective_config = getattr(processed, "configuration", None) or {}
            input_audio_sha = _hash_file(Path(processed.dsp_path))
            artifact_path = None
            if keep_asr_input:
                artifact_dir = out_dir / "artifacts" / "tier2" / clip.clip_id / condition
                artifact_dir.mkdir(parents=True, exist_ok=True)
                artifact_path = artifact_dir / "asr_input.wav"
                shutil.copyfile(processed.dsp_path, artifact_path)
            wer_value = evaluate.wer(clip.reference, text)
            cer_value = evaluate.cer(clip.reference, text)
            wer_edits, wer_ref_words = evaluate.wer_counts(clip.reference, text)
            cer_edits, cer_ref_chars = evaluate.cer_counts(clip.reference, text)
            term_recovered, term_eligible = evaluate.term_counts(clip.reference, text, clip.terms)
            term_acc, terms_present = evaluate.term_accuracy(clip.reference, text, clip.terms)
            term_presence_recall = None if term_eligible == 0 or term_acc != term_acc else float(term_acc)
            nshr = nshr_for_segments(transcript.segments, clip.speech_intervals)
            duration = _m3av_duration(clip, audio_duration)
            rtf = elapsed / max(duration, 1e-9)
            records.append(
                {
                    "tier": 2,
                    "dataset": "m3av",
                    "clip_id": clip.clip_id,
                    "audio_path": str(clip.audio_path),
                    "annotation_path": str(clip.annotation_path),
                    "audio_duration_s": duration,
                    "duration_bucket": duration_bucket(duration),
                    "condition": condition,
                    "wer": float(wer_value),
                    "cer": float(cer_value),
                    "wer_edits": int(wer_edits),
                    "wer_ref_count": int(wer_ref_words),
                    "wer_ref_words": int(wer_ref_words),
                    "cer_edits": int(cer_edits),
                    "cer_ref_count": int(cer_ref_chars),
                    "cer_ref_chars": int(cer_ref_chars),
                    "term_presence_recall": term_presence_recall,
                    "kter": term_presence_recall,
                    "term_source": "m3av_capitalized_heuristic",
                    "terms_source": "m3av_capitalized_heuristic",
                    "recovered_terms": int(term_recovered),
                    "eligible_terms": int(term_eligible),
                    "terms_recovered": int(term_recovered),
                    "terms_eligible": int(term_eligible),
                    "terms_present": int(term_eligible),
                    "reference": clip.reference,
                    "hypothesis": text,
                    "segments": segments_payload,
                    "effective_config": effective_config,
                    "input_audio_sha256": input_audio_sha,
                    "reference_sha256": _hash_text(clip.reference),
                    "hypothesis_sha256": _hash_text(text),
                    "asr_input_artifact": str(artifact_path) if artifact_path is not None else None,
                    "nshr": float(nshr),
                    "rtf": float(rtf),
                    "seconds": float(elapsed),
                    "language": transcript.language,
                    "dsp": processed.diagnostics,
                }
            )
            if getattr(args, "save_waveforms", False):
                wave_dir = out_dir / "waveforms" / "tier2" / clip.clip_id / condition
                _save_waveform_png(Path(processed.dsp_path), wave_dir / "waveform.png")
            completed.add(condition_key)
            if not keep_media:
                _atomic_write_json(
                    checkpoint_path,
                    {"schema_version": CHECKPOINT_SCHEMA_VERSION, "metric_version": METRIC_VERSION, "run_manifest": manifest, "records": records},
                )
                shutil.rmtree(media_root, ignore_errors=True)

    bucket_summary = aggregate_records(
        records,
        ["condition", "duration_bucket"],
        TIER2_METRICS,
        bootstrap_ci_enabled=getattr(args, "bootstrap_ci", False),
        n_boot=int(getattr(args, "bootstrap_samples", 2000)),
    )
    overall_summary = aggregate_records(
        records,
        ["condition"],
        TIER2_METRICS,
        bootstrap_ci_enabled=getattr(args, "bootstrap_ci", False),
        n_boot=int(getattr(args, "bootstrap_samples", 2000)),
    )
    for row in overall_summary:
        row["duration_bucket"] = "all"
    summary = bucket_summary + overall_summary
    write_json(out_dir / "tier2_m3av_results.json", records)
    write_json(out_dir / "tier2_m3av_summary.json", summary)
    write_csv(out_dir / "tier2_m3av_results.csv", records, TIER2_CSV)
    _atomic_write_json(checkpoint_path, {"schema_version": CHECKPOINT_SCHEMA_VERSION, "metric_version": METRIC_VERSION, "run_manifest": manifest, "records": records})
    return records, summary


def _parse_snrs(value: str) -> list[float | None]:
    tokens = [token.strip() for token in str(value).split(",") if token.strip()]
    if not tokens:
        return [None]
    result: list[float | None] = []
    for token in tokens:
        lowered = token.lower()
        if lowered in {"none", "clean", "inf"}:
            result.append(None)
        else:
            result.append(float(token))
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Tier 1 (ACL6060) and/or Tier 2 (M3AV) evaluation.")
    parser.add_argument("--tier", choices=["1", "2", "all"], default="all")
    parser.add_argument("--split", choices=["dev", "eval"], default="eval")
    parser.add_argument("--conditions", default=",".join(CONDITIONS))
    parser.add_argument("--snrs", default="none", help="Comma-separated SNRs; use 'none' for clean only")
    parser.add_argument("--noise", default="none", help="none, demand, or path to a WAV file")
    parser.add_argument("--demand-root", default=None)
    parser.add_argument("--demand-env", default=RELEVANT_DEMAND_ENVS[0])
    parser.add_argument("--demand-envs", default=",".join(RELEVANT_DEMAND_ENVS))
    parser.add_argument("--noise-seed", type=int, default=20260403)
    parser.add_argument("--m3av-root", default=None)
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--out", default="eval_results")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--no-resume", dest="resume", action="store_false")
    parser.add_argument("--checkpoint", default=None, help="optional checkpoint path; defaults to out/tier*_checkpoint.json")
    parser.add_argument("--keep-media", action="store_true", default=False, help="retain generated DSP media and mixed noise WAVs")
    parser.add_argument("--keep-asr-input", action="store_true", default=False, help="retain the exact WAV passed to ASR for every completed condition")
    parser.add_argument("--save-waveforms", action="store_true", default=False, help="write a PNG waveform image for the processed output of each completed condition")
    parser.add_argument("--bootstrap-ci", action="store_true", default=False, help="add percentile bootstrap confidence intervals to summary rows")
    parser.add_argument("--bootstrap-samples", type=int, default=2000, help="number of bootstrap resamples when --bootstrap-ci is set")
    parser.add_argument("--oa-weight", type=float, default=0.3, help="observed-audio blend weight for hp_wiener_oa, in [0, 1]")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    args.snrs = _parse_snrs(args.snrs)

    all_records: list[dict[str, Any]] = []
    all_summaries: list[dict[str, Any]] = []

    if args.tier in {"1", "all"}:
        records, summary = run_tier1(args)
        all_records.extend(records)
        all_summaries.append({"tier": 1, "split": args.split, "summary": summary})

    if args.tier in {"2", "all"}:
        records, summary = run_tier2(args)
        all_records.extend(records)
        all_summaries.extend({"tier": 2, "summary": summary})

    out_dir = Path(args.out).expanduser().resolve()
    metadata = {
        "deferred_metrics": ["DNSMOS"],
        "notes": [
            "Tier 1 and Tier 2 are reported separately and are never pooled.",
            "Sample sizes are small; standard deviations are reported and significance is not claimed.",
        ],
    }
    write_json(out_dir / "eval_run_metadata.json", metadata)
    print(json.dumps({"records": len(all_records), "summaries": len(all_summaries), "out": str(out_dir)}, indent=2))


if __name__ == "__main__":
    main()