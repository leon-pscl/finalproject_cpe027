import pandas as pd
import numpy as np
from pathlib import Path
from eval.model_wrapper import ASRModelWrapper
from eval.metrics import calculate_wer, calculate_accuracy

def run_benchmark(
    manifest_path="eval/manifests/eval_harness_manifest.csv",
    model_path="models/asr_model.pt", # Update to actual path
    output_report="eval/reports/benchmark_results.csv"
):
    # Setup paths
    report_path = Path(output_report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize model
    model_wrapper = ASRModelWrapper(model_path)
    
    # Load manifest
    print(f"Loading evaluation manifest from {manifest_path}...")
    df = pd.read_csv(manifest_path)
    
    if df.empty:
        print("Manifest is empty. No samples to evaluate.")
        return

    results = []

    print(f"Starting benchmark on {len(df)} samples...")
    for idx, row in df.iterrows():
        noisy_path = row['noisy_path']
        reference_text = row['text']
        env = row['environment']
        snr = row['snr']
        dataset = row['set']
        
        # Transcribe
        try:
            hypothesis = model_wrapper.transcribe(noisy_path)
        except Exception as e:
            print(f"Error transcribing {noisy_path}: {e}")
            hypothesis = ""

        # Calculate metrics
        wer = calculate_wer(reference_text, hypothesis)
        acc = calculate_accuracy(reference_text, hypothesis)
        
        results.append({
            "sample_id": idx,
            "set": dataset,
            "environment": env,
            "snr": snr,
            "reference": reference_text,
            "hypothesis": hypothesis,
            "wer": wer,
            "accuracy": acc
        })
        
        if (idx + 1) % 10 == 0:
            print(f"Processed {idx + 1}/{len(df)} samples...")

    # Save detailed results
    results_df = pd.DataFrame(results)
    results_df.to_csv(output_report, index=False)
    
    # Generate Summary Table
    print("\n--- Benchmark Summary ---")
    summary = results_df.groupby(['set', 'environment', 'snr'])[['wer', 'accuracy']].mean().reset_index()
    print(summary.to_string(index=False))
    
    summary_path = report_path.with_name("summary_report.csv")
    summary.to_csv(summary_path, index=False)
    
    print(f"\nDetailed report saved to: {output_report}")
    print(f"Summary report saved to: {summary_path}")

if __name__ == "__main__":
    # In a real run, provide the actual model path
    run_benchmark()
