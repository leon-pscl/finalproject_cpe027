"""Shared metric utilities for DSP evaluation.

Provides normalization, WER, CER, term accuracy, and key‑term error rate.
Uses rapidfuzz when available, with a pure-Python fallback.
"""

from __future__ import annotations

import re
from typing import List, Sequence, Tuple


def _levenshtein(seq1: Sequence, seq2: Sequence) -> int:
    try:
        from rapidfuzz.distance import Levenshtein

        return Levenshtein.distance(seq1, seq2)
    except ImportError:
        # Pure Python fallback for environments without rapidfuzz
        if len(seq1) < len(seq2):
            seq1, seq2 = seq2, seq1
        if len(seq2) == 0:
            return len(seq1)
        prev = list(range(len(seq2) + 1))
        for item1 in seq1:
            curr = [prev[0] + 1]
            for j, item2 in enumerate(seq2):
                cost = 0 if item1 == item2 else 1
                curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
            prev = curr
        return prev[-1]


def normalize(text: str) -> str:
    """Lower‑case, remove non‑word characters, collapse whitespace."""
    text = re.sub(r"[^\w\s']", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def wer(reference: str, hypothesis: str) -> float:
    ref, hyp = normalize(reference).split(), normalize(hypothesis).split()
    return _levenshtein(ref, hyp) / max(1, len(ref))


def cer(reference: str, hypothesis: str) -> float:
    ref, hyp = normalize(reference), normalize(hypothesis)
    return _levenshtein(ref, hyp) / max(1, len(ref))


def term_accuracy(reference: str, hypothesis: str, terms: List[str]) -> Tuple[float, int]:
    """Share of glossary terms present in the reference that also appear in the hypothesis."""
    ref = f" {normalize(reference)} "
    hyp = f" {normalize(hypothesis)} "
    present = [t for t in (normalize(t) for t in terms) if t and f" {t} " in ref]
    if not present:
        return float("nan"), 0
    matched = sum(f" {t} " in hyp for t in present)
    return matched / len(present), len(present)
