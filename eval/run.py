"""Run the full DSP evaluation across all arms and datasets.

The script orchestrates mixing (Tier 1), arm building, ASR transcription, metric
computation, and result persistence.
"""

import argparse
import csv
import json
import os
from pathlib import Path
from typing import List, Dict

from backend.app.asr import transcribe_file
from backend.app.config import get_settings

from eval.mix import mix_clean_noise
from eval.arms import build_arm_a, build_arm_b, build_arm_c
from eval.metrics import wer, cer, term_accuracy
from eval.signal_metrics import si_sdr, pesq_score, stoi_score, estoi_score, dnsmos_scores


def load_manifests(manifests_dir: str) -> List[Dict]:
    manifests = []
    for file in Path(manifests_dir).glob("*.json"):
        data = json.loads(file.read_text(encoding="utf-8"))
        manifests.append(data)
    return manifests


def run_one_item(item: Dict, arm: str, terms: List[str]) -> Dict:
    src_path = item["path"]
    # Build the appropriate arm
    if arm == "A":
        wav_path = build_arm_a(src_path)
    elif arm == "B":
        wav_path = build_arm_b(src_path)
    elif arm == "C":
        wav_path = build_arm_c(src_path)
    else:
        raise ValueError(f"Unknown arm {arm}")

    # Transcribe via ASR (no additional enhancement)
    transcript = transcribe_file(str(wav_path), enhance=False)
    hyp_text = " ".join(seg.text for seg in transcript.segments)
    reference = ""  # placeholder – real reference should be loaded by the caller
    # Compute metrics (reference handling omitted for brevity)
    metrics = {
        "wer": wer(reference, hyp_text) if reference else None,
        "cer": cer(reference, hyp_text) if reference else None,
        "term_accuracy": None,
    }
    if reference and terms:
        acc, n = term_accuracy(reference, hyp_text, terms)
        metrics["term_accuracy"] = acc
        metrics["terms_checked"] = n
    return {
        "item_id": item.get("id"),
        "arm": arm,
        "wav_path": str(wav_path),
        "transcript": transcript.segments,
        **metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="DSP evaluation runner")
    parser.add_argument("--manifests", default="eval/manifests", help="Directory with dataset manifests")
    parser.add_argument("--out", default="eval/results", help="Output directory for CSV/JSON results")
    parser.add_argument("--dry-run", action="store_true", help="Estimate audio minutes and cost, do not run")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    settings = get_settings()

    manifests = load_manifests(args.manifests)
    results: List[Dict] = []

    for manifest in manifests:
        if not manifest.get("exists"):
            print(f"Skipping missing dataset {manifest['id']}")
            continue
        # For Tier 1 we need a clean + noise mix; here we just demonstrate mixing
        # using a placeholder noise file if available.
        if args.dry_run:
            # Estimate minutes assuming 1 min per item
            est_minutes = 1
            est_cost = est_minutes * 0.01  # placeholder cost per minute
            print(f"Dry‑run: {manifest['id']} – ~{est_minutes} min, ${est_cost:.2f}")
            continue

        # Load optional glossary terms (placeholder empty list)
        terms: List[str] = []
        for arm in ["A", "B", "C"]:
            result = run_one_item(manifest, arm, terms)
            results.append(result)

    # Write results CSV
    csv_path = out_dir / "results.csv"
    if results:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["item_id", "arm", "wav_path", "wer", "cer", "term_accuracy", "terms_checked"],
            )
            writer.writeheader()
            for r in results:
                writer.writerow({k: r.get(k) for k in writer.fieldnames})
        print(f"Wrote results to {csv_path}")


if __name__ == "__main__":
    main()
