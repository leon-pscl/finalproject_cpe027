"""Paired A/B benchmark: does the production DSP pipeline improve ASR accuracy?

Every manifest sample is transcribed twice from the same noisy mix:

* arm ``noisy`` - ``dsp.load_audio`` -> ``dsp.strip_silence`` -> ASR
* arm ``dsp``   - ``dsp.load_audio`` -> ``dsp.enhance`` -> ``dsp.strip_silence`` -> ASR

Both arms are decoded and silence-stripped identically, so the only difference is
``dsp.enhance``, and both mirror the order ``backend.app.asr`` uses in production.
Pairing the arms on the same sample is what makes the per-sample ``delta_wer``
meaningful; averaging two independent runs would not be comparable.
"""

import os
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf

from backend.app import dsp
from backend.app.config import get_settings
from eval.harness.run_eval import _safe_stem
from eval.metrics import calculate_wer, calculate_accuracy, word_edits
from eval.model_wrapper import ASRModelWrapper
from eval.preprocessing.utils import normalize_text
from eval.report import bootstrap_delta

# Optional: test Groq LLM Answer Generator (used later in RAG pipelines)
try:
    from backend.app.answer_generator import GroqAnswerGenerator
except Exception:
    GroqAnswerGenerator = None


def _test_groq_endpoint() -> bool:
    """Transcribe a short silent WAV to verify the Groq Whisper endpoint works.
    Returns True on success, False on failure.
    """
    sr = 16000
    silence = np.zeros(int(0.5 * sr), dtype=np.float32)
    fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    # Write as 16-bit PCM to match Groq's expected format
    sf.write(tmp_path, silence, sr, subtype='PCM_16')
    try:
        wrapper = ASRModelWrapper()
        _ = wrapper.transcribe(tmp_path)  # Should succeed (may return empty string)
        return True
    except Exception as e:
        print(f"Groq endpoint test failed: {e}")
        return False
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def _test_openai_endpoint() -> bool:
    """Send a trivial prompt to the Groq LLM answer generator to verify the key.
    Returns True on success, False on failure.
    """
    if GroqAnswerGenerator is None:
        return True  # No generator available - skip the test
    try:
        gen = GroqAnswerGenerator()
        _ = gen.generate("What is 2+2?", [])
        return True
    except Exception as e:
        print(f"Groq LLM endpoint test failed: {e}")
        return False


def build_arms(src_path: str, out_dir: Path, stem: str) -> tuple[str, str, dict]:
    """Write the two decoded arms for `src_path` and return (noisy, dsp, dsp_report)."""
    s = get_settings()
    audio = dsp.load_audio(src_path)

    baseline, _ = dsp.strip_silence(audio)
    noisy_path = out_dir / f"{stem}__noisy.wav"
    dsp.write_wav(str(noisy_path), baseline)

    enhanced, report = dsp.enhance(
        audio,
        rt60=s.dsp_rt60,
        floor_db=s.dsp_floor_db,
        reverb_weight=s.dsp_reverb_weight,
        noise_bias=s.dsp_noise_bias,
    )
    stripped, _ = dsp.strip_silence(enhanced)
    dsp_path = out_dir / f"{stem}__dsp.wav"
    dsp.write_wav(str(dsp_path), stripped)

    return str(noisy_path), str(dsp_path), report.as_dict()


SUMMARY_COLUMNS = [
    "set", "environment", "snr", "n", "ref_words",
    "wer_noisy", "wer_dsp", "delta_wer", "delta_ci_low", "delta_ci_high",
    "acc_noisy", "acc_dsp",
]

# Enough resamples for a stable interval without making a 68-cell summary crawl.
CELL_BOOTSTRAP_ITERS = 2000


def summarise_cell(keys, cell) -> list:
    """One summary row: corpus WER per arm plus a paired CI on the difference.

    WER is pooled as sum(edits)/sum(ref_words) rather than averaged over utterances.
    The CI is bootstrapped over the per-sample deltas, which is only valid because
    both arms are decoded from the same sample.
    """
    ref_words = int(cell["ref_words"].sum())
    wer_noisy = int(cell["edits_noisy"].sum()) / max(1, ref_words)
    wer_dsp = int(cell["edits_dsp"].sum()) / max(1, ref_words)
    lo, hi = bootstrap_delta(
        cell["wer_noisy"].tolist(), cell["wer_dsp"].tolist(), n_iter=CELL_BOOTSTRAP_ITERS
    )
    return [
        *keys, len(cell), ref_words,
        wer_noisy, wer_dsp, wer_dsp - wer_noisy, lo, hi,
        max(0.0, 1.0 - wer_noisy), max(0.0, 1.0 - wer_dsp),
    ]


def run_benchmark(
    manifest_path: str = "eval/manifests/eval_harness_manifest.csv",
    model_path: str = "models/asr_model.pt",  # retained for compatibility, not used by Groq wrapper
    output_report: str = "eval/reports/benchmark_results.csv",
    arms_dir: str = "eval/results/arms",
    limit: int | None = None,
    resume: bool = True,
) -> None:
    """Run the paired noisy-vs-DSP benchmark and write detailed + summary CSVs.

    A full sweep is thousands of rate-limited ASR calls, so each scored sample is
    appended to `output_report` as it completes and `resume` skips samples already
    present. An interrupted run continues instead of starting over.
    """
    report_path = Path(output_report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    arms_path = Path(arms_dir)
    arms_path.mkdir(parents=True, exist_ok=True)

    # 1. Verify external APIs
    print("\n=== Testing API endpoints ===")
    if not _test_groq_endpoint():
        print("X Groq API test failed - aborting benchmark.")
        return
    if not _test_openai_endpoint():
        print("X Groq LLM API test failed - aborting benchmark.")
        return
    print("OK All endpoints reachable. Starting benchmark...\n")

    # 2. Initialize the ASR wrapper (Groq)
    model_wrapper = ASRModelWrapper(model_path)

    # 3. Load the manifest produced by the harness
    print(f"Loading evaluation manifest from {manifest_path}...")
    df = pd.read_csv(manifest_path)
    if df.empty:
        print("Manifest is empty. No samples to evaluate.")
        return

    # A sample with no reference cannot be scored; counting it as WER 1.0 (what the
    # metric returns for an empty reference) would drag every average to the floor.
    df["text"] = df["text"].fillna("").astype(str)
    missing_ref = int((df["text"].str.strip() == "").sum())
    df = df[df["text"].str.strip() != ""]
    before = len(df)
    df = df.drop_duplicates(subset=["noisy_path"]).reset_index(drop=True)
    if missing_ref:
        print(f"Skipping {missing_ref} sample(s) with no reference transcript.")
    if before != len(df):
        print(f"Dropped {before - len(df)} duplicate manifest row(s).")
    if limit:
        df = df.head(limit)

    # Resume: `noisy_path` identifies a sample, so it is what already-scored rows are
    # matched on. Dropping them here also skips their (expensive) DSP arm rebuild.
    done = set()
    if resume and report_path.exists():
        prev = pd.read_csv(report_path)
        if "noisy_path" in prev.columns:
            done = set(prev["noisy_path"].astype(str))
            df = df[~df["noisy_path"].astype(str).isin(done)]
            print(f"Resuming: {len(done)} sample(s) already scored in {report_path}.")
        else:
            # Pre-resume reports have no key to match on; starting over would append
            # rows to a file whose schema no longer matches.
            raise RuntimeError(
                f"{report_path} predates the resume support and cannot be appended to. "
                "Move it aside, or pass resume=False to overwrite it."
            )
    elif report_path.exists():
        report_path.unlink()

    if df.empty:
        print("No scorable samples left to run.")
        if not done:
            return

    # Rate limiter shared by both arms: each sample costs two ASR requests.
    rpm = int(os.getenv("GROQ_RPM", "20"))
    interval = 60.0 / rpm
    state = {"last": 0.0}

    def throttle():
        elapsed = time.time() - state["last"]
        if elapsed < interval:
            time.sleep(interval - elapsed)
        state["last"] = time.time()

    max_dur = float(os.getenv("MAX_DURATION_SECONDS", "30"))
    total = len(df)
    print(f"Starting paired benchmark on {total} samples ({total * 2} ASR requests)...")

    def append_row(row_dict):
        """Flush one scored sample so an interrupted run keeps what it paid for."""
        header = not report_path.exists()
        pd.DataFrame([row_dict]).to_csv(
            report_path, mode="a", header=header, index=False, encoding="utf-8"
        )

    for idx, row in df.iterrows():
        noisy_src = row["noisy_path"]
        # Sanitized: Loquacious ids embed colons, which Windows rejects in a path.
        stem = _safe_stem(f"{row['set']}_{row.get('id', idx)}_{row['environment']}_{row['snr']}dB")
        try:
            noisy_arm, dsp_arm, dsp_report = build_arms(noisy_src, arms_path, stem)
        except Exception as e:
            print(f"WARN Arm build failed for {noisy_src}: {e} - skipping sample.")
            continue

        # Skip long files on the stripped baseline (the length actually sent to ASR).
        audio, sr = sf.read(noisy_arm)
        duration = len(audio) / sr
        if duration > max_dur:
            continue

        reference_text = row["text"]
        print(f"\n--- Sample {idx + 1}/{total} ---")
        print(f"Source    : {noisy_src}")
        print(f"Dataset   : {row['set']}, Env: {row['environment']}, SNR: {row['snr']} dB")

        try:
            throttle()
            hyp_noisy = model_wrapper.transcribe(noisy_arm)
            throttle()
            hyp_dsp = model_wrapper.transcribe(dsp_arm)
        except Exception as e:
            print(f"WARN Transcription failed for {stem}: {e}")
            print("Aborting benchmark due to ASR error.")
            break

        wer_noisy = calculate_wer(reference_text, hyp_noisy)
        wer_dsp = calculate_wer(reference_text, hyp_dsp)
        # Raw counts as well as the ratios: corpus WER is sum(edits)/sum(ref_words),
        # which is the figure ASR papers quote. Averaging per-utterance ratios instead
        # weights a 4-word sample the same as a 40-word one.
        ref_words = len(normalize_text(reference_text).split())
        edits_noisy = word_edits(reference_text, hyp_noisy)
        edits_dsp = word_edits(reference_text, hyp_dsp)

        append_row({
            "sample_id": row.get("id", idx),
            "noisy_path": noisy_src,
            "set": row["set"],
            "environment": row["environment"],
            "snr": row["snr"],
            "reference": reference_text,
            "hyp_noisy": hyp_noisy,
            "hyp_dsp": hyp_dsp,
            "ref_words": ref_words,
            "edits_noisy": edits_noisy,
            "edits_dsp": edits_dsp,
            "wer_noisy": wer_noisy,
            "wer_dsp": wer_dsp,
            "delta_wer": wer_dsp - wer_noisy,   # negative = DSP helped
            "acc_noisy": calculate_accuracy(reference_text, hyp_noisy),
            "acc_dsp": calculate_accuracy(reference_text, hyp_dsp),
            "snr_before_db": dsp_report.get("snr_est_before_db"),
            "snr_after_db": dsp_report.get("snr_est_after_db"),
        })
        print(f"WER noisy: {wer_noisy:.4f} | WER dsp: {wer_dsp:.4f} | delta: {wer_dsp - wer_noisy:+.4f}")

    # 6. Summarise whatever is on disk, so an interrupted run still reports.
    summary_path = report_path.with_name("summary_report.csv")
    if not report_path.exists():
        print("\nNo results were generated (all samples may have been skipped).")
        pd.DataFrame(columns=SUMMARY_COLUMNS).to_csv(summary_path, index=False)
        print(f"Summary report (empty) saved to: {summary_path}")
        return
    results_df = pd.read_csv(report_path)
    if results_df.empty:
        print("\nNo results were generated (all samples may have been skipped).")
        pd.DataFrame(columns=SUMMARY_COLUMNS).to_csv(summary_path, index=False)
        print(f"Summary report (empty) saved to: {summary_path}")
        return

    # 7. Summary report
    summary = pd.DataFrame(
        [summarise_cell(keys, cell) for keys, cell in
         results_df.groupby(["set", "environment", "snr"], sort=True)],
        columns=SUMMARY_COLUMNS,
    )
    print("\n--- Benchmark Summary (negative delta_wer = DSP helped) ---")
    print(summary.to_string(index=False))
    overall = summarise_cell(("ALL", "ALL", "ALL"), results_df)
    print(
        f"\nOverall (corpus WER over {overall[3]} paired samples / {overall[4]} ref words): "
        f"{overall[5]:.4f} -> {overall[6]:.4f}, "
        f"delta {overall[7]:+.4f}, 95% CI [{overall[8]:+.4f}, {overall[9]:+.4f}]"
    )
    if overall[8] <= 0 <= overall[9]:
        print("  CI spans 0: this sample count cannot distinguish the two arms.")
    summary.to_csv(summary_path, index=False)
    print(f"\nDetailed report saved to: {output_report}")
    print(f"Summary report saved to: {summary_path}")


if __name__ == "__main__":
    run_benchmark()
