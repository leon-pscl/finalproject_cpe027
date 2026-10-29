"""Run the full DSP evaluation across arms and datasets.

Orchestrates mixing (Tier 1), arm building (Arm A, B, C), ASR transcription,
metric computation (WER, CER, Key-Term Accuracy), and result persistence to CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Dict, List

# Safe encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root and backend directory are in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from eval.metrics import cer, term_accuracy, wer


def load_manifests(manifests_dir: str) -> List[Dict]:
    manifests = []
    p = Path(manifests_dir)
    if not p.exists():
        return manifests

    # Check for JSON manifests
    for file in p.glob("*.json"):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                manifests.extend(data)
            else:
                manifests.append(data)
        except Exception:
            continue

    # Check for CSV manifests / inventories if no JSON items found
    if not manifests:
        for file in p.glob("*.csv"):
            try:
                with open(file, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        manifests.append({
                            "id": row.get("id") or row.get("item_id") or file.stem,
                            "path": row.get("path") or row.get("audio_path") or "",
                            "exists": os.path.exists(row.get("path", "")),
                            "reference": row.get("transcript") or row.get("reference") or "",
                        })
            except Exception:
                continue

    return manifests


def run_one_item(item: Dict, arm: str, terms: List[str]) -> Dict:
    # Lazy import arms and transcriber so dry-run or light environments don't require heavy dependencies
    try:
        from app.asr import transcribe_file
    except ImportError:
        from backend.app.asr import transcribe_file

    from eval.arms import build_arm_a, build_arm_b, build_arm_c

    src_path = item["path"]
    if arm == "A":
        wav_path = build_arm_a(src_path)
    elif arm == "B":
        wav_path = build_arm_b(src_path)
    elif arm == "C":
        wav_path = build_arm_c(src_path)
    else:
        raise ValueError(f"Unknown arm {arm}")

    # Transcribe via ASR with enhancement disabled (arms handle DSP)
    try:
        transcript = transcribe_file(str(wav_path), enhance=False)
        hyp_text = " ".join(seg.text for seg in transcript.segments)
    except Exception as exc:
        print(f"Warning: transcription failed for {src_path} (arm {arm}): {exc}")
        hyp_text = ""
        transcript = None

    reference = item.get("reference") or item.get("transcript_text") or ""
    metrics = {
        "wer": wer(reference, hyp_text) if reference and hyp_text else None,
        "cer": cer(reference, hyp_text) if reference and hyp_text else None,
        "term_accuracy": None,
        "terms_checked": 0,
    }

    if reference and hyp_text and terms:
        acc, n = term_accuracy(reference, hyp_text, terms)
        metrics["term_accuracy"] = acc
        metrics["terms_checked"] = n

    return {
        "item_id": item.get("id", Path(src_path).stem),
        "arm": arm,
        "wav_path": str(wav_path),
        "hypothesis": hyp_text,
        **metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="DSP evaluation runner")
    parser.add_argument("--manifests", default="eval/manifests", help="Directory with dataset manifests")
    parser.add_argument("--out", default="eval/results", help="Output directory for CSV results")
    parser.add_argument("--dry-run", action="store_true", help="Estimate audio minutes and cost, do not run")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifests = load_manifests(args.manifests)

    # Check for local samples if manifest datasets are empty or external
    sample_files = list(Path("samples").glob("*.wav")) + list(Path("samples").glob("*.m4a")) + list(Path("samples").glob("*.mp3"))
    for sf in sample_files:
        ref_txt = sf.with_suffix(".txt")
        ref = ref_txt.read_text(encoding="utf-8") if ref_txt.exists() else ""
        manifests.append({
            "id": f"sample-{sf.stem}",
            "path": str(sf),
            "exists": True,
            "reference": ref,
        })

    if not manifests:
        print("No evaluation manifests or sample files found.")
        print("Tip: Run `python eval/generate_manifests.py` or place recordings in `samples/`.")
        return

    print(f"Loaded {len(manifests)} items across manifests.")
    results: List[Dict] = []
    ready_count = 0
    missing_count = 0

    for item in manifests:
        item_id = item.get("id", "unnamed")
        exists = item.get("exists", False)
        path = item.get("path", "")

        if not exists or not os.path.exists(path):
            missing_count += 1
            continue

        ready_count += 1
        if args.dry_run:
            est_minutes = 1.0
            est_cost = est_minutes * 0.006  # approx hosted ASR cost
            print(f"[Dry-run] Ready: {item_id} - ~{est_minutes:.1f} min, ~${est_cost:.3f}")
            continue

        terms: List[str] = item.get("terms", [])
        for arm in ["A", "B", "C"]:
            print(f"Processing {item_id} (Arm {arm})...")
            try:
                res = run_one_item(item, arm, terms)
                results.append(res)
            except Exception as e:
                print(f"Error on {item_id} Arm {arm}: {e}")

    if args.dry_run:
        print(f"\n[Dry-run Summary] Ready local items: {ready_count}, Missing external dataset items: {missing_count}")
        if missing_count > 0:
            print("Note: External datasets (E:\\Datasets) not mounted on this machine. Local samples/ ready for evaluation.")

    # Write results CSV
    csv_path = out_dir / "results.csv"
    if results:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            fieldnames = ["item_id", "arm", "wav_path", "wer", "cer", "term_accuracy", "terms_checked"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow({k: r.get(k) for k in fieldnames})
        print(f"\n[OK] Evaluation complete. Results saved to: {csv_path}")
    elif not args.dry_run and ready_count == 0:
        print("\nNo items were processed (check dataset paths in EVAL_DATA_ROOT or samples/).")


if __name__ == "__main__":
    main()
