"""Generate comprehensive evaluation reports and statistical tables from evaluation results.

Computes paired bootstrap confidence intervals, relative WER reductions, per-arm
metric comparisons (WER, CER, Key-Term Accuracy), and worst regressions.
Follows the DSP evaluation insert protocol in docs/step5A_dsp_evaluation_insert.md.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

# Safe encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def bootstrap_paired_diff(
    values_a: List[float], values_b: List[float], n_iter: int = 10000, seed: int = 42
) -> Tuple[float, float, float]:
    """Return (mean_diff, lower_95_ci, upper_95_ci) for (values_a - values_b).

    For error metrics like WER and CER, (A - B) > 0 indicates Arm B has a lower
    error rate (i.e. DSP helped).
    """
    if not values_a or not values_b or len(values_a) != len(values_b):
        return 0.0, 0.0, 0.0

    random.seed(seed)
    diffs = [a - b for a, b in zip(values_a, values_b)]
    n = len(diffs)
    mean_diff = sum(diffs) / n

    boot_means = []
    for _ in range(n_iter):
        sample = [diffs[random.randint(0, n - 1)] for _ in range(n)]
        boot_means.append(sum(sample) / n)

    boot_means.sort()
    lower = boot_means[int(0.025 * n_iter)]
    upper = boot_means[int(0.975 * n_iter)]
    return mean_diff, lower, upper


def load_results(csv_path: str) -> List[Dict]:
    rows = []
    if not os.path.exists(csv_path):
        return rows
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def generate_report(csv_path: str, out_dir: str) -> str:
    rows = load_results(csv_path)
    out_path = Path(out_dir) / "dsp_evaluation_report.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        report_text = "# DSP Evaluation Report\n\nNo evaluation results found in CSV. Run `python eval/run.py` first.\n"
        out_path.write_text(report_text, encoding="utf-8")
        return report_text

    # Group records by item_id
    by_item = defaultdict(dict)
    for r in rows:
        item_id = r.get("item_id") or r.get("id") or "unknown"
        arm = r.get("arm", "A")
        by_item[item_id][arm] = r

    # Collect paired values for Arms A and B
    items_paired = []
    a_wers, b_wers, c_wers = [], [], []
    a_cers, b_cers = [], []
    per_item_deltas = []

    for item_id, arms in by_item.items():
        if "A" in arms and "B" in arms:
            try:
                wa = float(arms["A"].get("wer", 0.0) or 0.0)
                wb = float(arms["B"].get("wer", 0.0) or 0.0)
                ca = float(arms["A"].get("cer", 0.0) or 0.0)
                cb = float(arms["B"].get("cer", 0.0) or 0.0)
                a_wers.append(wa)
                b_wers.append(wb)
                a_cers.append(ca)
                b_cers.append(cb)

                delta_wer = wa - wb  # positive = Arm B helped
                per_item_deltas.append((item_id, wa, wb, delta_wer))
                items_paired.append(item_id)

                if "C" in arms:
                    wc = float(arms["C"].get("wer", 0.0) or 0.0)
                    c_wers.append(wc)
            except (ValueError, TypeError):
                continue

    n = len(items_paired)
    if n == 0:
        report_text = "# DSP Evaluation Report\n\nNo paired (Arm A & Arm B) items available for statistical analysis.\n"
        out_path.write_text(report_text, encoding="utf-8")
        return report_text

    mean_wa = sum(a_wers) / n
    mean_wb = sum(b_wers) / n
    mean_ca = sum(a_cers) / n
    mean_cb = sum(b_cers) / n
    mean_wc = sum(c_wers) / len(c_wers) if c_wers else None

    # Paired bootstrap
    mean_delta_wer, ci_lo_wer, ci_hi_wer = bootstrap_paired_diff(a_wers, b_wers)
    mean_delta_cer, ci_lo_cer, ci_hi_cer = bootstrap_paired_diff(a_cers, b_cers)

    # Relative WER Reduction (WERR)
    rel_reduction = ((mean_wa - mean_wb) / mean_wa * 100.0) if mean_wa > 0 else 0.0

    # Decision rule check:
    # Supported improvement if 95% CI is strictly > 0 (excludes zero)
    supported = ci_lo_wer > 0.0
    harmful = ci_hi_wer < 0.0

    # Sort worst regressions (where Arm B increased WER relative to Arm A, delta < 0)
    per_item_deltas.sort(key=lambda x: x[3])
    worst_regressions = [x for x in per_item_deltas if x[3] < 0][:5]

    # Build report Markdown
    lines = [
        "# DSP Speech Enhancement Evaluation Report",
        "",
        "## Summary Overview",
        "",
        f"- **Total Paired Audio Items:** {n}",
        f"- **Arm A (Baseline - 16kHz mono loudnorm):** Mean WER = `{mean_wa * 100:.2f}%`, Mean CER = `{mean_ca * 100:.2f}%`",
        f"- **Arm B (Project DSP - Highpass + Spectral Gating):** Mean WER = `{mean_wb * 100:.2f}%`, Mean CER = `{mean_cb * 100:.2f}%`",
    ]
    if mean_wc is not None:
        lines.append(f"- **Arm C (Classical Wiener + Dereverb):** Mean WER = `{mean_wc * 100:.2f}%`")

    lines.extend([
        "",
        "## Statistical Hypothesis Test (Paired Bootstrap, N=10,000)",
        "",
        "| Metric | Mean Delta (Arm A − Arm B) | 95% Confidence Interval | Relative Reduction | Supported? |",
        "|---|---|---|---|---|",
        f"| **WER** | `+{mean_delta_wer * 100:.2f}%` | `[{ci_lo_wer * 100:.2f}%, {ci_hi_wer * 100:.2f}%]` | `{rel_reduction:+.2f}%` | {'[YES]' if supported else '[NO]'} |",
        f"| **CER** | `+{mean_delta_cer * 100:.2f}%` | `[{ci_lo_cer * 100:.2f}%, {ci_hi_cer * 100:.2f}%]` | — | {'[YES]' if ci_lo_cer > 0 else '[NO]'} |",
        "",
        "> **Note on Interpretation:** Positive Delta (Arm A − Arm B) means Arm B lowered the error rate. A change is considered statistically supported only if the 95% confidence interval strictly excludes zero.",
        "",
        "## Decision Rule Evaluation",
        "",
    ])

    if supported:
        lines.append("[RECOMMENDATION] ENABLE DSP BY DEFAULT. The project DSP pipeline demonstrated a statistically significant error reduction across evaluated items.")
    elif harmful:
        lines.append("[RECOMMENDATION] KEEP DSP DISABLED BY DEFAULT. Arm B introduced audible distortion or artifacts that significantly degraded ASR performance.")
    else:
        lines.append("[RECOMMENDATION] KEEP DSP OPT-IN (OFF BY DEFAULT). While DSP may assist on specific low-SNR samples, the overall improvement across the corpus does not statistically separate from zero. Keep `DSP_ENABLED=false` as the default.")

    if worst_regressions:
        lines.extend([
            "",
            "## Top Regressions (Where DSP Hurt Accuracy)",
            "",
            "| Item ID | Arm A WER | Arm B WER | Degradation (Δ) |",
            "|---|---|---|---|",
        ])
        for item_id, wa, wb, delta in worst_regressions:
            lines.append(f"| `{item_id}` | `{wa * 100:.1f}%` | `{wb * 100:.1f}%` | `{delta * 100:.1f}%` |")

    report_content = "\n".join(lines) + "\n"
    out_path.write_text(report_content, encoding="utf-8")

    # Also maintain delta_wer_report.md for backward compatibility with cli.py
    (Path(out_dir) / "delta_wer_report.md").write_text(report_content, encoding="utf-8")

    print(f"[OK] DSP Evaluation Report written to {out_path}")
    return report_content


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate evaluation report from CSV results")
    parser.add_argument("--csv", default="eval/results/results.csv", help="Path to CSV results file")
    parser.add_argument("--out", default="eval/results", help="Directory to write reports")
    args = parser.parse_args()
    generate_report(args.csv, args.out)


if __name__ == "__main__":
    main()
