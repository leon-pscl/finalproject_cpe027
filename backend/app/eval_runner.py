"""Dataset-aware ASR/DSP evaluation runner.

Tier 1 evaluates ACL6060, including seeded noise injection. Tier 2 evaluates
unmodified M3AV clips. Tiers are reported separately and never pooled.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

from . import asr, dsp, evaluate
from .config import EVAL_DATA_ROOT, get_settings
from .eval_data import (
    AclTalk,
    M3avClip,
    aggregate_records,
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


CONDITIONS = ("arm_a", "hp", "hp+sg")
TIER1_METRICS = ["wer", "cer", "kter", "signal_snr_improvement_db", "rtf", "seconds"]
TIER2_METRICS = ["wer", "cer", "kter", "rtf", "seconds", "nshr"]
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
    "terms_present",
    "nshr",
    "rtf",
    "audio_duration_s",
    "seconds",
    "language",
]
RELEVANT_DEMAND_ENVS = ("DKITCHEN", "DLIVING", "DWASHING")


def _load_checkpoint(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "records": []}
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {"schema_version": 1, "records": []}
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        return {"schema_version": 1, "records": []}
    return payload


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


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


def _condition_config(condition: str, settings: Any) -> DSPConfig:
    if condition == "arm_a":
        return DSPConfig(
            bypass=True,
            high_pass_enabled=False,
            spectral_gating_enabled=False,
            normalize=True,
            target_sample_rate=16000,
            target_channels=1,
        )
    if condition == "hp":
        return DSPConfig(
            bypass=False,
            high_pass_enabled=True,
            high_pass_cutoff_hz=float(settings.dsp_high_pass_cutoff_hz),
            spectral_gating_enabled=False,
            normalize=True,
            target_sample_rate=16000,
            target_channels=1,
        )
    if condition == "hp+sg":
        return DSPConfig(
            bypass=False,
            high_pass_enabled=True,
            high_pass_cutoff_hz=float(settings.dsp_high_pass_cutoff_hz),
            spectral_gating_enabled=True,
            spectral_gating_strength_db=25.0,
            normalize=True,
            target_sample_rate=16000,
            target_channels=1,
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
    if not resume and checkpoint_path.exists():
        checkpoint_path.unlink(missing_ok=True)

    noise_type, noise_file = _tier1_noise_file(args)
    demand_envs = [item.strip() for item in str(args.demand_envs).split(",") if item.strip()]
    if noise_type == "demand" and not demand_envs:
        demand_envs = list(RELEVANT_DEMAND_ENVS)
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
    for condition in conditions:
        if condition not in CONDITIONS:
            raise ValueError(f"unknown condition: {condition}")

    if resume:
        checkpoint = _load_checkpoint(checkpoint_path)
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
                    config = _condition_config(condition, settings)
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
                    wer_value = evaluate.wer(talk.reference, text)
                    cer_value = evaluate.cer(talk.reference, text)
                    term_acc, terms_present = evaluate.term_accuracy(talk.reference, text, talk.terms)
                    kter_value = 0.0 if terms_present == 0 or term_acc != term_acc else float(term_acc)
                    rtf = elapsed / max(audio_duration, 1e-9)
                    improvement = None
                    if is_noisy:
                        enhanced_audio = dsp.load_audio(processed.dsp_path)
                        improvement = snr_improvement_db(clean_audio, noisy_audio, enhanced_audio)
                        if improvement != improvement:
                            improvement = None

                    print(
                        f"    WER {wer_value:.1%} | CER {cer_value:.1%} | "
                        f"KTER {kter_value:.1%} | RTF {rtf:.2f} | {elapsed:.1f}s",
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
                            "kter": float(kter_value),
                            "terms_present": int(terms_present),
                            "signal_snr_improvement_db": _safe_float(improvement),
                            "rtf": float(rtf),
                            "seconds": float(elapsed),
                            "language": transcript.language,
                            "dsp": processed.diagnostics,
                        }
                    )
                    completed.add(condition_key)
                    if not keep_media:
                        _atomic_write_json(
                            checkpoint_path,
                            {"schema_version": 1, "records": records},
                        )
                        shutil.rmtree(media_root, ignore_errors=True)

                if is_noisy and noisy_path is not None and not keep_media:
                    try:
                        noisy_path.unlink(missing_ok=True)
                    except OSError:
                        pass

    group_keys = ["condition", "noise_type", "snr_db"]
    summary = aggregate_records(records, group_keys, TIER1_METRICS)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "tier1_acl_results.json", records)
    write_json(out_dir / "tier1_acl_summary.json", summary)
    write_csv(out_dir / "tier1_acl_results.csv", records, TIER1_CSV)
    _atomic_write_json(checkpoint_path, {"schema_version": 1, "records": records})
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
    if not resume and checkpoint_path.exists():
        checkpoint_path.unlink(missing_ok=True)

    conditions = [item.strip() for item in str(args.conditions).split(",") if item.strip()]
    for condition in conditions:
        if condition not in CONDITIONS:
            raise ValueError(f"unknown condition: {condition}")

    if resume:
        checkpoint = _load_checkpoint(checkpoint_path)
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
            config = _condition_config(condition, settings)
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
            wer_value = evaluate.wer(clip.reference, text)
            cer_value = evaluate.cer(clip.reference, text)
            term_acc, terms_present = evaluate.term_accuracy(clip.reference, text, clip.terms)
            kter_value = 0.0 if terms_present == 0 or term_acc != term_acc else float(term_acc)
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
                    "kter": float(kter_value),
                    "terms_present": int(terms_present),
                    "nshr": float(nshr),
                    "rtf": float(rtf),
                    "seconds": float(elapsed),
                    "language": transcript.language,
                    "dsp": processed.diagnostics,
                }
            )
            completed.add(condition_key)
            if not keep_media:
                _atomic_write_json(
                    checkpoint_path,
                    {"schema_version": 1, "records": records},
                )
                shutil.rmtree(media_root, ignore_errors=True)

    bucket_summary = aggregate_records(records, ["condition", "duration_bucket"], TIER2_METRICS)
    overall_summary = aggregate_records(records, ["condition"], TIER2_METRICS)
    for row in overall_summary:
        row["duration_bucket"] = "all"
    summary = bucket_summary + overall_summary
    write_json(out_dir / "tier2_m3av_results.json", records)
    write_json(out_dir / "tier2_m3av_summary.json", summary)
    write_csv(out_dir / "tier2_m3av_results.csv", records, TIER2_CSV)
    _atomic_write_json(checkpoint_path, {"schema_version": 1, "records": records})
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