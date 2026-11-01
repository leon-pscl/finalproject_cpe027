import numpy as np

from .preprocessing.utils import normalize_text

# Both sides of every comparison go through normalize_text (upper-case, bracketed
# asides dropped, punctuation to spaces). The datasets store references already
# normalized this way -- Loquacious ships ALL CAPS, no punctuation -- while Whisper
# returns true-case text with punctuation, so scoring raw strings reports ~100% WER
# for a perfect transcript. Normalizing one side only was the original bug.

def wer(reference, hypothesis):
    """Word Error Rate – thin wrapper around calculate_wer for backward compatibility."""
    return calculate_wer(reference, hypothesis)

def cer(reference, hypothesis):
    """Character Error Rate – Levenshtein distance on characters.
    Returns the edit distance divided by the number of reference characters.
    """
    ref_chars = list(normalize_text(reference))
    hyp_chars = list(normalize_text(hypothesis))
    if len(ref_chars) == 0:
        return float('inf') if hyp_chars else 0.0
    distance = edit_distance(ref_chars, hyp_chars)
    return distance / len(ref_chars)

def term_accuracy(reference, hypothesis, terms):
    """Simple term‑accuracy placeholder.
    Counts how many of the supplied `terms` appear in both reference and hypothesis.
    Returns (accuracy, count_of_terms). If `terms` is empty returns (None, 0).
    """
    if not terms:
        return None, 0
    ref_n = normalize_text(reference)
    hyp_n = normalize_text(hypothesis)
    matches = sum(1 for term in terms
                  if normalize_text(term) in ref_n and normalize_text(term) in hyp_n)
    acc = matches / len(terms)
    return acc, len(terms)

def edit_distance(s1, s2):
    """Calculates the Levenshtein distance between two sequences."""
    s1 = np.array(s1)
    s2 = np.array(s2)

    if len(s1) < len(s2):
        return edit_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]

def calculate_wer(reference, hypothesis):
    """
    Calculates Word Error Rate (WER).
    WER = (S + D + I) / N
    """
    ref_words = normalize_text(reference).split()
    hyp_words = normalize_text(hypothesis).split()

    if not ref_words:
        return float('inf') if hyp_words else 0.0

    distance = edit_distance(ref_words, hyp_words)
    return distance / len(ref_words)

def word_edits(reference, hypothesis):
    """Raw word-level edit count (S + D + I), the numerator of WER.

    Reported alongside the ratio so a corpus WER can be pooled correctly as
    sum(edits) / sum(ref_words); a mean of per-utterance ratios is not the same
    number and over-weights short utterances.
    """
    ref_words = normalize_text(reference).split()
    hyp_words = normalize_text(hypothesis).split()
    if not ref_words:
        return len(hyp_words)
    return int(edit_distance(ref_words, hyp_words))


def calculate_accuracy(reference, hypothesis):
    """Word accuracy = 1 - WER, floored at 0 (WER can exceed 1 on insertions).

    The previous implementation zipped the two word lists positionally, so a single
    inserted or deleted word misaligned the rest and scored ~0 for an otherwise
    correct transcript.
    """
    rate = calculate_wer(reference, hypothesis)
    if rate == float('inf'):
        return 0.0
    return max(0.0, 1.0 - rate)
