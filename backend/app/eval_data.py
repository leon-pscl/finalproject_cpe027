"""Shared, dependency-light helpers for the Tier 1 / Tier 2 evaluation harness."""

from __future__ import annotations

import csv
import json
import math
import os
import re
import statistics
import xml.etree.ElementTree as ET
import zlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .config import EVAL_DATA_ROOT

BRACKETED_TERM_RE = re.compile(r"\[([^\]]+)\]")
CAPITALISED_TERM_RE = re.compile(r"\b[A-Z][A-Za-z0-9]*(?:[-'][A-Za-z0-9]+)*\b")
ACRONYM_RE = re.compile(r"\b[A-Z]{2,}[0-9]*\b")


@dataclass(frozen=True)
class AclTalk:
    """One ACL6060 talk with its clean (reference) transcript and term list."""

    talk_id: str
    split: str
    audio_path: Path
    reference: str
    terms: list[str]


@dataclass(frozen=True)
class M3avClip:
    """One M3AV lecture recording with transcript, heuristic terms and speech spans."""

    clip_id: str
    root: Path
    audio_path: Path
    annotation_path: Path
    reference: str
    terms: list[str]
    duration_seconds: float
    speech_intervals: list[tuple[float, float]]


def _rms(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=np.float64).ravel()
    if x.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(x * x)))


def _align_to_reference(reference: np.ndarray, estimate: np.ndarray) -> np.ndarray:
    reference = np.asarray(reference, dtype=np.float64).ravel()
    estimate = np.asarray(estimate, dtype=np.float64).ravel()
    if estimate.size == reference.size:
        return estimate
    if estimate.size >= reference.size:
        return estimate[: reference.size]
    return np.pad(estimate, (0, reference.size - estimate.size))


def acl6060_root(data_root: Path | str | None = None) -> Path:
    """Locate the ACL6060 dataset root, defaulting to EVAL_DATA_ROOT."""
    base = Path(data_root or EVAL_DATA_ROOT).expanduser()
    candidate = base / "(ACL6060)2023.iwslt-1.2.dataset" / "2" / "acl_6060"
    if candidate.is_dir():
        return candidate
    # Allow callers to point at the dataset root directly.
    if (base / "dev" / "full_wavs").is_dir() or (base / "eval" / "full_wavs").is_dir():
        return base
    raise FileNotFoundError(
        f"ACL6060 dataset root not found under {base}; expected .../acl_6060"
    )


def _xml_root(xml_path: Path) -> ET.Element:
    """Parse ACL XML, tolerating the unescaped ampersands present in some talks."""
    raw = xml_path.read_text(encoding="utf-8")
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        sanitized = re.sub(
            r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9A-Fa-f]+;)", "&amp;", raw
        )
        return ET.fromstring(sanitized)


def parse_acl_xml_reference(xml_path: Path | str) -> dict[str, str]:
    """Return `{talk_id: reference transcript}` from an ACL6060 XML file."""
    path = Path(xml_path).expanduser()
    root = _xml_root(path)
    references: dict[str, str] = {}
    for doc in root.findall(".//doc"):
        talk_id = (doc.findtext("talkid") or doc.get("docid") or "").strip()
        if not talk_id:
            continue
        parts: list[str] = []
        for segment in doc.findall(".//seg"):
            text = (segment.text or "").strip()
            if text:
                parts.append(text)
        references[talk_id] = " ".join(parts)
    return references


def extract_bracketed_terms(text: str) -> list[str]:
    """Extract the technical terms written as `[term]` in ACL tagged transcripts."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in BRACKETED_TERM_RE.findall(text or ""):
        term = raw.strip()
        key = term.lower()
        if term and key not in seen:
            seen.add(key)
            result.append(term)
    return result


def load_acl_talks(
    split: str, data_root: Path | str | None = None
) -> list[AclTalk]:
    """Load one ACL6060 split (dev/eval) into talk records."""
    split = split.strip().lower()
    if split not in {"dev", "eval"}:
        raise ValueError("ACL6060 split must be 'dev' or 'eval'")
    root = acl6060_root(data_root) / split
    xml_path = root / "text" / "xml" / f"ACL.6060.{split}.en-xx.en.xml"
    references = parse_acl_xml_reference(xml_path)

    tagged_path = (
        root / "text" / "tagged_terminology" / f"ACL.6060.{split}.tagged.en-xx.en.txt"
    )
    terms = extract_bracketed_terms(tagged_path.read_text(encoding="utf-8")) if tagged_path.is_file() else []

    audio_dir = root / "full_wavs"
    result: list[AclTalk] = []
    for talk_id in sorted(references):
        reference = references[talk_id].strip()
        if not reference:
            continue
        audio_path = audio_dir / f"{talk_id}.wav"
        if not audio_path.is_file():
            continue
        result.append(
            AclTalk(
                talk_id=talk_id,
                split=split,
                audio_path=audio_path,
                reference=reference,
                terms=list(terms),
            )
        )
    return result


def mix_noise(
    clean: np.ndarray,
    noise: np.ndarray,
    snr_db: float,
    seed: int | None = None,
) -> np.ndarray:
    """Add a seeded noise segment to clean speech at the requested SNR."""
    clean = np.asarray(clean, dtype=np.float32).ravel()
    noise = np.asarray(noise, dtype=np.float32).ravel()
    if clean.size == 0:
        raise ValueError("clean audio must not be empty")
    if noise.size == 0:
        raise ValueError("noise audio must not be empty")
    if math.isinf(snr_db) and snr_db > 0:
        return clean.copy()

    rng = np.random.default_rng(0 if seed is None else seed)
    if noise.size > clean.size:
        start = int(rng.integers(0, noise.size - clean.size + 1))
        segment = noise[start : start + clean.size]
    else:
        repetitions = math.ceil(clean.size / noise.size)
        segment = np.tile(noise, repetitions)[: clean.size]

    clean_rms = _rms(clean)
    noise_rms = _rms(segment)
    if noise_rms <= 1e-12:
        return clean.copy()
    target_noise_rms = clean_rms / (10.0 ** (float(snr_db) / 20.0))
    scaled_noise = segment * (target_noise_rms / noise_rms)
    return np.asarray(clean + scaled_noise, dtype=np.float32)


def snr_db(reference: Any, estimate: Any) -> float:
    """Signal-to-noise ratio in dB for estimate against a clean reference."""
    reference_arr = _align_to_reference(np.asarray(reference), np.asarray(estimate))
    estimate_arr = _align_to_reference(np.asarray(estimate), np.asarray(reference))
    if reference_arr.size == 0:
        return float("-inf")
    signal_power = float(np.mean(reference_arr * reference_arr))
    noise_power = float(np.mean((estimate_arr - reference_arr) ** 2))
    if signal_power <= 0.0:
        return float("-inf")
    if noise_power <= 0.0:
        return float("inf")
    return 10.0 * math.log10(signal_power / noise_power)


def snr_improvement_db(
    clean_reference: Any, noisy_input: Any, enhanced_output: Any
) -> float:
    """Improvement in signal-level SNR from noisy input to enhanced output."""
    baseline = snr_db(clean_reference, noisy_input)
    enhanced = snr_db(clean_reference, enhanced_output)
    if not math.isfinite(baseline) or not math.isfinite(enhanced):
        return float("nan")
    return float(enhanced - baseline)


def noise_seed_for(
    base_seed: int, talk_id: str, noise_key: str, snr_db: float | None
) -> int:
    """Deterministic seed shared across conditions for the same noisy input."""
    snr_label = "inf" if snr_db is None else format(float(snr_db), ".6g")
    label = f"{base_seed}:{talk_id}:{noise_key}:{snr_label}"
    return int(zlib.crc32(label.encode("utf-8")) & 0xFFFFFFFF)


def discover_demand_envs(root: Path | str) -> list[str]:
    """Return sorted environment directory names below a DEMAND root."""
    base = Path(root).expanduser()
    if not base.is_dir():
        return []
    return sorted(path.name for path in base.iterdir() if path.is_dir())


def demand_noise_file(env_root: Path | str) -> Path:
    """Pick the first channel WAV in an extracted DEMAND environment folder."""
    base = Path(env_root).expanduser()
    # Convenience normalization: DEMAND folders are commonly named *_16k.
    if not base.is_dir() and not base.name.endswith("_16k"):
        suffixed = base.with_name(f"{base.name}_16k")
        if suffixed.is_dir():
            base = suffixed
    if not base.is_dir():
        raise FileNotFoundError(f"DEMAND environment folder not found: {base}")
    files = sorted(base.glob("*.wav"))
    if not files:
        # Some extractions keep channel files one level deeper.
        files = sorted(base.rglob("*.wav"))
    if not files:
        raise FileNotFoundError(f"No WAV files found in {base}")
    return files[0]


def load_noise_audio(path: Path | str) -> np.ndarray:
    """Load a noise file through the same decoder used by ASR."""
    from . import dsp

    return dsp.load_audio(str(Path(path).expanduser()))


# ---- M3AV helpers ---------------------------------------------------------


M3AV_STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "because",
    "between",
    "but",
    "from",
    "have",
    "into",
    "not",
    "that",
    "the",
    "their",
    "this",
    "which",
    "with",
    "your",
}


def _find_audio_file(clip_root: Path) -> Path | None:
    direct = [
        clip_root / "audio.wav",
        clip_root / "audio.flac",
        clip_root / "audio.mp4",
        clip_root / "audio.m4a",
        clip_root / "audio.mkv",
        clip_root / f"{clip_root.name}.wav",
        clip_root / f"{clip_root.name}.flac",
        clip_root / f"{clip_root.name}.mp4",
        clip_root / f"{clip_root.name}.m4a",
    ]
    for path in direct:
        if path.is_file():
            return path
    for subdir in ("raw", "video", "media"):
        candidate_dir = clip_root / subdir
        if candidate_dir.is_dir():
            for ext in (".wav", ".mp4", ".m4a", ".mkv", ".mov"):
                matches = sorted(candidate_dir.glob(f"*{ext}"))
                if matches:
                    return matches[0]
    media_exts = {".wav", ".flac", ".mp4", ".m4a", ".mkv", ".mov", ".avi"}
    found = sorted(
        path
        for path in clip_root.rglob("*")
        if path.is_file() and path.suffix.lower() in media_exts
    )
    return found[0] if found else None


def extract_m3av_key_terms(sentences: Iterable[str], max_terms: int = 25) -> list[str]:
    """Heuristic key-term list derived from OCR/paper text for M3AV clips."""
    seen: set[str] = set()
    result: list[str] = []
    for sentence in sentences or []:
        for candidate in CAPITALISED_TERM_RE.findall(str(sentence)):
            if ACRONYM_RE.fullmatch(candidate) is None and len(candidate) < 4:
                continue
            if candidate.lower() in M3AV_STOPWORDS:
                continue
            key = candidate.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(candidate)
            if len(result) >= max_terms:
                return result
    # Fall back to acronyms if ordinary capitalised words are unavailable.
    if not result:
        seen = set()
        for sentence in sentences or []:
            for candidate in ACRONYM_RE.findall(str(sentence)):
                key = candidate.lower()
                if key in seen:
                    continue
                seen.add(key)
                result.append(candidate)
                if len(result) >= max_terms:
                    return result
    return result


def merge_intervals(intervals: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    """Merge overlapping/touching timestamp intervals."""
    cleaned: list[tuple[float, float]] = []
    for start, end in intervals:
        try:
            lo, hi = float(start), float(end)
        except (TypeError, ValueError):
            continue
        if hi >= lo:
            cleaned.append((lo, hi))
    if not cleaned:
        return []
    cleaned.sort()
    merged = [cleaned[0]]
    for start, end in cleaned[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def parse_m3av_annotation(annotation_path: Path | str) -> tuple[str, float, list[tuple[float, float]], list[str]]:
    """Parse M3AV `final+timestamps.json` into text, duration, speech spans and sentences."""
    path = Path(annotation_path).expanduser()
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        entries = [entries]

    text_parts: list[str] = []
    sentences: list[str] = []
    intervals: list[tuple[float, float]] = []
    max_end = 0.0

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        final = entry.get("final_written") or entry.get("final_spoken")
        if isinstance(final, str) and final.strip():
            text_parts.append(final.strip())
        if isinstance(entry.get("paper_sentences"), list):
            sentences.extend(str(item) for item in entry["paper_sentences"] if item)
        for word in entry.get("words_spoken") or []:
            if not isinstance(word, dict):
                continue
            start = word.get("start")
            end = word.get("end")
            if isinstance(start, (int, float)) and isinstance(end, (int, float)):
                lo, hi = float(start), float(end)
                intervals.append((lo, hi))
                max_end = max(max_end, hi)

    # Paper sentences are usually a separate file; the annotation may not contain them.
    reference = " ".join(text_parts).strip()
    paper_path = path.parent.parent / "paper" / "paper_sentences.json"
    if paper_path.is_file():
        try:
            paper_data = json.loads(paper_path.read_text(encoding="utf-8"))
            if isinstance(paper_data, list):
                sentences.extend(str(item) for item in paper_data if item)
        except (OSError, json.JSONDecodeError):
            pass
    terms = extract_m3av_key_terms(sentences, max_terms=25)
    speech_intervals = merge_intervals(intervals)
    return reference, float(max_end), speech_intervals, terms


def m3av_root(data_root: Path | str | None = None) -> Path:
    """Locate an extracted M3AV root, defaulting under EVAL_DATA_ROOT."""
    base = Path(data_root or EVAL_DATA_ROOT).expanduser()
    candidates = [
        base / "M3AV" / "extracted",
        base / "M3AV" / "local" / "extracted",
        base / "M3AV",
        base,
    ]
    for candidate in candidates:
        if candidate.is_dir() and _any_m3av_clip(candidate):
            return candidate
    # Last-resort fallback so a meaningful error can be raised by callers.
    return base / "M3AV" / "extracted"


def _any_m3av_clip(root: Path) -> bool:
    try:
        for child in root.iterdir():
            if child.is_dir() and (child / "speech" / "final+timestamps.json").is_file():
                return True
    except OSError:
        return False
    return False


def load_m3av_clips(data_root: Path | str | None = None) -> list[M3avClip]:
    """Load all M3AV clips from an extracted root."""
    root = m3av_root(data_root)
    if not root.is_dir() or not _any_m3av_clip(root):
        raise FileNotFoundError(
            f"M3AV extracted clips not found under {root}; expected clip/speech/final+timestamps.json"
        )
    result: list[M3avClip] = []
    for clip_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        annotation_path = clip_dir / "speech" / "final+timestamps.json"
        if not annotation_path.is_file():
            continue
        audio_path = _find_audio_file(clip_dir)
        if audio_path is None or not audio_path.is_file():
            continue
        reference, duration, speech_intervals, terms = parse_m3av_annotation(annotation_path)
        if not reference:
            continue
        result.append(
            M3avClip(
                clip_id=clip_dir.name,
                root=clip_dir,
                audio_path=audio_path,
                annotation_path=annotation_path,
                reference=reference,
                terms=terms,
                duration_seconds=duration,
                speech_intervals=speech_intervals,
            )
        )
    return result


def nshr_for_segments(
    asr_segments: Iterable[Any], speech_intervals: list[tuple[float, float]]
) -> float:
    """Non-speech hallucination rate for a list of timestamped ASR segments."""
    segments = list(asr_segments)
    if not segments:
        return 0.0
    merged = merge_intervals(speech_intervals)
    hallucinated = 0
    for segment in segments:
        if isinstance(segment, tuple):
            start, end = segment
        else:
            start = getattr(segment, "start", None)
            end = getattr(segment, "end", None)
        try:
            lo, hi = float(start), float(end)
        except (TypeError, ValueError):
            continue
        if not any(max(lo, s) < min(hi, e) for s, e in merged):
            hallucinated += 1
    return hallucinated / len(segments)


def duration_bucket(seconds: float) -> str:
    if seconds < 300.0:
        return "<5m"
    if seconds < 600.0:
        return "5-10m"
    if seconds < 1200.0:
        return "10-20m"
    return ">=20m"


def aggregate_records(
    records: list[dict[str, Any]],
    group_keys: list[str],
    metric_keys: list[str],
    bootstrap_ci_enabled: bool = False,
    n_boot: int = 2000,
    seed: int = 42,
) -> list[dict[str, Any]]:

    """Group records and return mean/sample-stdev for each metric."""
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in records:
        key = tuple(record.get(key) for key in group_keys)
        groups.setdefault(key, []).append(record)

    result: list[dict[str, Any]] = []
    for key, members in sorted(groups.items(), key=lambda item: [str(x) for x in item[0]]):
        row: dict[str, Any] = {}
        for index, key_name in enumerate(group_keys):
            row[key_name] = key[index]
        row["count"] = len(members)
        row["unique_talks"] = len(
            {record.get("talk_id", record.get("clip_id")) for record in members}
        )
        row["unique_speakers"] = None
        for metric in metric_keys:
            values = [
                float(record[metric])
                for record in members
                if isinstance(record.get(metric), (int, float))
                and math.isfinite(float(record[metric]))
            ]
            if values:
                row[f"{metric}_mean"] = float(statistics.fmean(values))
                row[f"{metric}_std"] = (
                    float(statistics.stdev(values)) if len(values) > 1 else None
                )
            else:
                row[f"{metric}_mean"] = None
                row[f"{metric}_std"] = None
            row[f"{metric}_valid_observations"] = len(values)

            edit_key = f"{metric}_edits"
            ref_key = f"{metric}_ref_count"
            edit_total = sum(
                int(record[edit_key])
                for record in members
                if isinstance(record.get(edit_key), (int, float))
            )
            ref_total = sum(
                int(record[ref_key])
                for record in members
                if isinstance(record.get(ref_key), (int, float))
            )
            if ref_total > 0:
                row[f"{metric}_corpus"] = edit_total / ref_total
                row[f"{metric}_edit_count"] = edit_total
                row[f"{metric}_reference_count"] = ref_total
            else:
                row[f"{metric}_corpus"] = None
                row[f"{metric}_edit_count"] = None
                row[f"{metric}_reference_count"] = None
            if bootstrap_ci_enabled:
                ci = bootstrap_ci(values, n_boot=n_boot, seed=seed)
                row[f"{metric}_ci_mean"] = ci["mean"]
                row[f"{metric}_ci_lower"] = ci["lower"]
                row[f"{metric}_ci_upper"] = ci["upper"]
                row[f"{metric}_ci"] = ci
        result.append(row)
    return result


def bootstrap_ci(
    values: list[float],
    n_boot: int = 2000,
    confidence: float = 0.95,
    seed: int = 42,
) -> dict[str, float | None]:
    """Percentile bootstrap confidence interval for the mean of `values`.

    Returns a dict with ``mean``, ``lower``, and ``upper`` keys.  For fewer
    than two observations the interval is ``None``.
    """
    arr = np.asarray(values, dtype=np.float64).ravel()
    if arr.size == 0:
        return {"mean": None, "lower": None, "upper": None}
    if arr.size < 2:
        return {"mean": float(arr[0]), "lower": None, "upper": None}
    rng = np.random.default_rng(seed)
    boot_means = np.empty(n_boot, dtype=np.float64)
    for i in range(n_boot):
        sample = rng.choice(arr, size=arr.size, replace=True)
        boot_means[i] = float(np.mean(sample))
    alpha = (1.0 - confidence) / 2.0
    return {
        "mean": float(np.mean(arr)),
        "lower": float(np.percentile(boot_means, 100.0 * alpha)),
        "upper": float(np.percentile(boot_means, 100.0 * (1.0 - alpha))),
    }
def write_json(path: Path | str, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, allow_nan=False)


def write_csv(path: Path | str, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in columns})