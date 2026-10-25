"""Raw vs enhanced transcription comparison (objective 1.5).

    python -m app.evaluate --audio /samples/lecture.m4a --reference /samples/lecture.txt \\
        [--terms /samples/terms.txt] [--reverb-weight 0.3] [--out /samples/results]

Runs the SAME model on: raw audio | denoise only | denoise + dereverberation, and reports
WER, CER, technical-term accuracy, processing time and the DSP report. Nothing is assumed:
whichever condition scores lowest WER on your recordings is the one to keep.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time

from rapidfuzz.distance import Levenshtein

from . import dsp
from .asr import get_model, transcribe_file


def normalize(text: str) -> str:
    text = re.sub(r"[^\w\s']", " ", text.lower(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def wer(reference: str, hypothesis: str) -> float:
    ref, hyp = normalize(reference).split(), normalize(hypothesis).split()
    return Levenshtein.distance(ref, hyp) / max(1, len(ref))


def cer(reference: str, hypothesis: str) -> float:
    ref, hyp = normalize(reference), normalize(hypothesis)
    return Levenshtein.distance(ref, hyp) / max(1, len(ref))


def term_accuracy(reference: str, hypothesis: str, terms: list[str]) -> tuple[float, int]:
    """Share of glossary terms present in the reference that the hypothesis also contains."""
    ref, hyp = f" {normalize(reference)} ", f" {normalize(hypothesis)} "
    present = [t for t in (normalize(t) for t in terms) if t and f" {t} " in ref]
    if not present:
        return float("nan"), 0
    return sum(f" {t} " in hyp for t in present) / len(present), len(present)


def run_condition(path: str, **kwargs) -> tuple[str, float, dict | None, str | None]:
    t0 = time.time()
    result = transcribe_file(path, **kwargs)
    text = " ".join(s.text for s in result.segments)
    return text, time.time() - t0, result.dsp, result.language


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--reference", required=True, help="text file with the correct transcript")
    ap.add_argument("--terms", help="text file, one technical term per line")
    ap.add_argument("--reverb-weight", type=float, default=0.3, help="dereverberation strength to test (0-1)")
    ap.add_argument("--out", default="results")
    args = ap.parse_args()

    reference = open(args.reference, encoding="utf-8").read()
    terms = [l.strip() for l in open(args.terms, encoding="utf-8")] if args.terms else []
    os.makedirs(args.out, exist_ok=True)

    get_model()  # load once up-front so model loading is not counted in any condition's time
    conditions = [
        ("raw", dict(enhance=False)),
        ("denoise", dict(enhance=True, reverb_weight=0.0)),
        (f"denoise+dereverb({args.reverb_weight})", dict(enhance=True, reverb_weight=args.reverb_weight)),
    ]
    rows = []
    for name, kw in conditions:
        print(f"running {name} ...", flush=True)
        text, secs, report, lang = run_condition(args.audio, **kw)
        acc, n_terms = term_accuracy(reference, text, terms) if terms else (float("nan"), 0)
        rows.append({"condition": name, "wer": wer(reference, text), "cer": cer(reference, text),
                     "term_accuracy": acc, "terms_checked": n_terms, "seconds": secs,
                     "language": lang, "dsp": report})
        with open(os.path.join(args.out, re.sub(r"\W+", "_", name) + ".txt"), "w", encoding="utf-8") as f:
            f.write(text)
        if kw.get("enhance"):
            x, _ = dsp.enhance(dsp.load_audio(args.audio), reverb_weight=kw.get("reverb_weight", 0.0))
            dsp.write_wav(os.path.join(args.out, re.sub(r"\W+", "_", name) + ".wav"), x)  # listen to it

    base = rows[0]["wer"]
    print(f"\n{'condition':<28}{'WER':>8}{'CER':>8}{'terms':>9}{'time(s)':>9}{'vs raw':>10}")
    for r in rows:
        terms_s = "n/a" if r["terms_checked"] == 0 else f"{r['term_accuracy']:.0%}"
        delta = "" if r is rows[0] else f"{(r['wer'] - base) * 100:+.1f} pt"
        print(f"{r['condition']:<28}{r['wer']:>8.1%}{r['cer']:>8.1%}{terms_s:>9}{r['seconds']:>9.1f}{delta:>10}")
    best = min(rows, key=lambda r: r["wer"])
    print(f"\nLowest WER on this recording: {best['condition']}  (one recording is an anecdote - test several)")
    json.dump(rows, open(os.path.join(args.out, "results.json"), "w"), indent=2)
    print(f"Saved transcripts, enhanced WAVs and results.json in {args.out}/")


if __name__ == "__main__":
    main()
