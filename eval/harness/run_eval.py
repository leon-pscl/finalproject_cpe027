import os
import json
import pandas as pd
import soundfile as sf
import io
import numpy as np
import librosa
from pathlib import Path
from eval.harness.mixer import NoiseMixer

TARGET_SR = 16000  # Consistent sample rate for mixing

def load_audio(path):
    """Loads audio from either a wav file or a parquet file and resamples to TARGET_SR if needed."""
    if path.endswith('.parquet'):
        # LoquaciousSet stores audio as bytes in a parquet file
        df = pd.read_parquet(path)
        # Assume the first row contains the target audio
        # Look for common audio column names
        for col in ['audio', 'bytes', 'data', 'wav']:
            if col in df.columns:
                audio_bytes = df[col].iloc[0]
                # Handle HuggingFace‑style dicts
                if isinstance(audio_bytes, dict):
                    audio_bytes = audio_bytes.get('bytes')
                with io.BytesIO(audio_bytes) as buf:
                    audio, sr = sf.read(buf)
                    break
        else:
            raise ValueError(f"No audio column found in parquet file {path}")
    else:
        audio, sr = sf.read(path)
    # Resample to TARGET_SR if needed and ensure mono
    if sr != TARGET_SR:
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        audio = librosa.resample(audio, orig_sr=sr, target_sr=TARGET_SR)
        sr = TARGET_SR
    else:
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
    return audio, sr

def run_harness(
    clean_manifests={
        "acl": "eval/manifests/acl_manifest.csv",
        "loq": "eval/manifests/loq_manifest.csv"
    },
    noise_bank_path="eval/manifests/noise_bank.json",
    output_dir=r"E:\EvalWork\noisy_samples",
    snrs=[0, 5, 10, 20],
    envs=None # If None, use all from noise bank
):
    """Run the evaluation harness with caching and resume support.
    
    This function now:
    * Loads any existing manifest to avoid re‑processing already generated samples.
    * Checks for existing output files before mixing (direct write – safe on Windows).
    * Uses a persistent noise cache inside ``NoiseMixer`` to avoid re‑reading noise files.
    * Ensures all audio (clean and noise) is resampled to a common ``TARGET_SR`` before mixing.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Initialise mixer with the target sample rate
    mixer = NoiseMixer(noise_bank_path, target_sr=TARGET_SR)
    with open(noise_bank_path, 'r') as f:
        noise_bank = json.load(f)
    target_envs = envs if envs else list(noise_bank.keys())

    manifest_path = "eval/manifests/eval_harness_manifest.csv"
    if os.path.exists(manifest_path):
        existing_df = pd.read_csv(manifest_path)
        processed = set(
            zip(
                existing_df['original_path'],
                existing_df['environment'],
                existing_df['snr']
            )
        )
        all_results = existing_df.to_dict('records')
    else:
        processed = set()
        all_results = []

    # Sequential processing (stable on Windows)
    for set_name, manifest_path_clean in clean_manifests.items():
        print(f"Processing set: {set_name}...")
        df = pd.read_csv(manifest_path_clean)
        if set_name == "acl" and 'is_clean' in df.columns:
            df = df[df['is_clean'] == True]
        for _, row in df.iterrows():
            audio_path = row['path']
            text = row.get('text', row.get('transcript', ''))
            combos = [(env, snr) for env in target_envs for snr in snrs
                      if (audio_path, env, snr) not in processed]
            if not combos:
                continue
            try:
                clean_audio, sr = load_audio(audio_path)
            except Exception as e:
                print(f"\n  Error reading {audio_path}: {e}")
                continue
            for env, snr in combos:
                try:
                    noisy_audio = mixer.mix(clean_audio, env, snr)
                    stem = Path(audio_path).stem
                    filename = f"{set_name}_{stem}_{env}_{snr}dB.wav"
                    save_path = out_path / filename
                    sf.write(save_path, noisy_audio, TARGET_SR)
                    all_results.append({
                        "original_path": audio_path,
                        "noisy_path": str(save_path),
                        "text": text,
                        "environment": env,
                        "snr": snr,
                        "set": set_name
                    })
                    processed.add((audio_path, env, snr))
                except Exception as e:
                    print(f"\n  Error mixing {audio_path} with {env} at {snr}dB: {e}")

    results_df = pd.DataFrame(all_results)
    results_df.to_csv(manifest_path, index=False)
    print(f"\nHarness complete. Manifest saved to {manifest_path}")

if __name__ == "__main__":
    run_harness()
