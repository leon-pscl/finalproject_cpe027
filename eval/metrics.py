import numpy as np

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
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    
    if not ref_words:
        return float('inf') if hyp_words else 0.0
    
    distance = edit_distance(ref_words, hyp_words)
    return distance / len(ref_words)

def calculate_accuracy(reference, hypothesis):
    """Calculates simple word-level accuracy."""
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    
    if not ref_words:
        return 0.0 if hyp_words else 1.0
        
    matches = 0
    for r, h in zip(ref_words, hyp_words):
        if r == h:
            matches += 1
            
    return matches / len(ref_words)
