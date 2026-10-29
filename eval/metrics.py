"""Shared metric utilities for DSP evaluation.

Provides normalization, WER, CER, term accuracy, and key‑term error rate. Uses the same
implementations as `backend/app/evaluate.py` to keep results consistent.
"""

import re
from typing import List, Tuple

from rapidfuzz.distance import Levenshtein


def normalize(text: str) -> str:
    """Lower‑case, remove non‑word characters, collapse whitespace."""
    text = re.sub(r"[^\w\s']", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def wer(reference: str, hypothesis: str) -> float:
    ref, hyp = normalize(reference).split(), normalize(hypothesis).split()
    return Levenshtein.distance(ref, hyp) / max(1, len(ref))


def cer(reference: str, hypothesis: str) -> float:
    ref, hyp = normalize(reference), normalize(hypothesis)
    return Levenshtein.distance(ref, hyp) / max(1, len(ref))


def term_accuracy(reference: str, hypothesis: str, terms: List[str]) -> Tuple[float, int]:
    """Share of glossary terms present in the reference that also appear in the hypothesis."""
    ref = f" {normalize(reference)} "
    hyp = f" {normalize(hypothesis)} "
    present = [t for t in (normalize(t) for t in terms) if t and f" {t} " in ref]
    if not present:
        return float("nan"), 0
    matched = sum(f" {t} " in hyp for t in present)
    return matched / len(present), len(present)
