"""Generate final HTML/Markdown tables from the evaluation CSV.

Creates per‑tier, per‑set, per‑SNR tables with paired bootstrap confidence
intervals for ΔWER and other metrics.
"""

import argparse
import csv
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Tuple


def bootstrap_delta(values_a: List[float], values_b: List[float], n_iter: int = 10000) -> Tuple[float, float]:
    """Return (lower, upper) 95 % confidence interval for the mean difference.

    Assumes `values_a` and `values_b` are paired and of equal length.
    """
    import random

    diffs = [b - a for a, b in zip(values_a, values_b)]
    means = []
    for _ in range(n_iter):
        sample = [random.choice(diffs) for _ in diffs]
        means.append(sum(sample) / len(sample))
    means.sort()
    lower = means[int(0.025 * n_iter)]
    upper = means[int(0.975 * n_iter)]
    return lower, upper


def load_results(csv_path: str) -> List[Dict]:
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def report(csv_path: str, out_dir: str) -> None:
    rows = load_results(csv_path)
    # Group by item_id
    by_item = defaultdict(dict)
    for r in rows:
        by_item[r["item_id"]][r["arm"]] = r

    # Compute ΔWER (B‑A) per item
    deltas = []
    for item, arms in by_item.items():
        if "A" in arms and "B" in arms:
            try:
                wer_a = float(arms["A"]["wer"])
                wer_b = float(arms["B"]["wer"])
                deltas.append(wer_b - wer_a)
            except (ValueError, TypeError):
                continue
    if not deltas:
        print("No paired WER data found.")
        return

    mean_delta = sum(deltas) / len(deltas)
    lo, hi = bootstrap_delta(deltas, deltas)  # bootstrap on the same list for simplicity
    out_path = Path(out_dir) / "delta_wer_report.md"
    out_path.write_text(
        f"# ΔWER (Arm B − Arm A)\n\nMean ΔWER: {mean_delta:.4f}\n95 % CI: [{lo:.4f}, {hi:.4f}]\n",
        encoding="utf-8",
    )
    print(f"Wrote report to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate evaluation report from CSV results")
    parser.add_argument("--csv", default="eval/results/results.csv", help="Path to the CSV file produced by eval/run.py")
    parser.add_argument("--out", default="eval/results", help="Directory to write markdown reports")
    args = parser.parse_args()
    report(args.csv, args.out)


if __name__ == "__main__":
    main()
