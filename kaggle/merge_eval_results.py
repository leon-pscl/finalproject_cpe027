"""Merge batch evaluation outputs into final Tier 1 / Tier 2 results.

Usage:
    python merge_eval_results.py --batch-dir <dir> --out <dir> [--bootstrap] [--bootstrap-samples N]

Batch layout expected under --batch-dir (as produced by the Kaggle notebook):
    <batch-dir>/tier1_*_results.json          -> Tier 1 batch result files
    <batch-dir>/tier2_*_results.json          -> Tier 2 batch result files

Final outputs written into --out:
    tier1_acl_results.json / .csv / tier1_acl_summary.json
    tier2_m3av_results.json / .csv / tier2_m3av_summary.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app import eval_data, eval_runner  # noqa: E402


def _dedupe_tier1(records: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for r in records:
        key = (r.get("split"), r.get("talk_id"), r.get("condition"), r.get("noise_type"), r.get("snr_db"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _dedupe_tier2(records: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for r in records:
        key = (r.get("clip_id"), r.get("condition"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    args = parser.parse_args()

    batch_dir = Path(args.batch_dir)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    tier1_files = sorted(
        p
        for p in batch_dir.rglob("*")
        if p.is_file() and p.name.startswith("tier1_") and p.name.endswith("_results.json")
    )
    tier2_files = sorted(
        p
        for p in batch_dir.rglob("*")
        if p.is_file() and p.name.startswith("tier2_") and p.name.endswith("_results.json")
    )

    tier1_records: list[dict] = []
    for path in tier1_files:
        tier1_records.extend(json.loads(path.read_text(encoding="utf-8")))
    tier2_records: list[dict] = []
    for path in tier2_files:
        tier2_records.extend(json.loads(path.read_text(encoding="utf-8")))

    final_t1 = _dedupe_tier1(tier1_records)
    final_t2 = _dedupe_tier2(tier2_records)

    eval_data.write_json(out_dir / "tier1_acl_results.json", final_t1)
    eval_data.write_csv(out_dir / "tier1_acl_results.csv", final_t1, eval_runner.TIER1_CSV)
    summary_t1 = eval_data.aggregate_records(
        final_t1,
        ["condition", "noise_type", "snr_db"],
        eval_runner.TIER1_METRICS,
        bootstrap_ci_enabled=args.bootstrap,
        n_boot=args.bootstrap_samples,
    )
    eval_data.write_json(out_dir / "tier1_acl_summary.json", summary_t1)

    eval_data.write_json(out_dir / "tier2_m3av_results.json", final_t2)
    eval_data.write_csv(out_dir / "tier2_m3av_results.csv", final_t2, eval_runner.TIER2_CSV)
    bucket_summary = eval_data.aggregate_records(
        final_t2,
        ["condition", "duration_bucket"],
        eval_runner.TIER2_METRICS,
        bootstrap_ci_enabled=args.bootstrap,
        n_boot=args.bootstrap_samples,
    )
    overall_summary = eval_data.aggregate_records(
        final_t2,
        ["condition"],
        eval_runner.TIER2_METRICS,
        bootstrap_ci_enabled=args.bootstrap,
        n_boot=args.bootstrap_samples,
    )
    for row in overall_summary:
        row["duration_bucket"] = "all"
    eval_data.write_json(out_dir / "tier2_m3av_summary.json", bucket_summary + overall_summary)

    print(
        json.dumps(
            {
                "tier1_records": len(final_t1),
                "tier2_records": len(final_t2),
                "tier1_batches": len(tier1_files),
                "tier2_batches": len(tier2_files),
                "out": str(out_dir),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
