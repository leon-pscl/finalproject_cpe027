#!/usr/bin/env python
"""One‑click DSP evaluation → CSV (and optional markdown report).

Usage examples:
    python eval/cli.py                 # full run, writes CSV and report
    python eval/cli.py --dry-run       # only estimates minutes / cost
    python eval/cli.py --skip-report   # skip markdown generation
    python eval/cli.py --force-manifests  # regenerate manifests even if they exist

The script expects the external evaluation datasets to be reachable via the
environment variable ``EVAL_DATA_ROOT`` (default ``E:\Datasets``).
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _run_cmd(cmd: list[str]) -> None:
    """Execute a command, printing it first and raising on error."""
    print(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)


def main() -> None:
    parser = argparse.ArgumentParser(description="One‑shot DSP evaluation → CSV")
    parser.add_argument("--root", help="Override EVAL_DATA_ROOT path")
    parser.add_argument("--dry-run", action="store_true", help="Only estimate minutes / cost")
    parser.add_argument("--skip-report", action="store_true", help="Do not generate markdown report")
    parser.add_argument(
        "--force-manifests",
        action="store_true",
        help="Regenerate dataset manifests even if they already exist",
    )
    args = parser.parse_args()

    # ---------------------------------------------------------------------
    # 1️⃣ Ensure the data root is set
    data_root = args.root or os.getenv("EVAL_DATA_ROOT", r"E:\Datasets")
    os.environ["EVAL_DATA_ROOT"] = data_root
    print(f"EVAL_DATA_ROOT set to: {data_root}\n")

    # ---------------------------------------------------------------------
    # 2️⃣ (Re)generate manifests if needed
    manifests_dir = Path("eval/manifests")
    if args.force_manifests or not any(manifests_dir.iterdir()):
        _run_cmd([sys.executable, "eval/generate_manifests.py"])
    else:
        print("Manifests already present – skipping generation (use --force-manifests to redo)\n")

    # ---------------------------------------------------------------------
    # 3️⃣ Run the full evaluation
    run_cmd = [sys.executable, "eval/run.py", "--manifests", str(manifests_dir), "--out", "eval/results"]
    if args.dry_run:
        run_cmd.append("--dry-run")
    _run_cmd(run_cmd)

    csv_path = Path("eval/results/results.csv")
    print(f"\n✅ Evaluation finished – CSV written to: {csv_path.resolve()}")

    # ---------------------------------------------------------------------
    # 4️⃣ Optional markdown report
    if not args.skip_report:
        report_cmd = [
            sys.executable,
            "eval/report.py",
            "--csv",
            str(csv_path),
            "--out",
            "eval/results",
        ]
        _run_cmd(report_cmd)
        print("📊 Markdown report generated (delta_wer_report.md)\n")
    else:
        print("🛑 Report generation skipped (use --skip-report to omit)\n")


if __name__ == "__main__":
    main()
