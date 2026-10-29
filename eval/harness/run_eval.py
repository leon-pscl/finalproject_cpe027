import os
import json
import pandas as pd
import soundfile as sf
import io
import numpy as np
from pathlib import Path
from eval.harness.mixer import NoiseMixer

def load_audio(path):
    """Loads audio from either a wav file or a parquet file."""
    if path.endswith('.parquet'):
        # LoquaciousSet stores audio as bytes in a parquet file
        df = pd.read_parquet(path)
        # Assume the first row contains the target audio
        # We look for common audio column names
        for col in ['audio', 'bytes', 'data']:
            if col in df.columns:
                audio_bytes = df[col].iloc[0]
                # Handle case where audio_bytes is a dict (HuggingFace style)
                if isinstance(audio_bytes, dict):
                    audio_bytes = audio_bytes.get('bytes')
                
                with io.BytesIO(audio_bytes) as buf:
                    audio, sr = sf.read(buf)
                    return audio, sr
        raise ValueError(f"No audio column found in parquet file {path}")
    else:
        return sf.read(path)

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
    # Setup paths
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    mixer = NoiseMixer(noise_bank_path)
    with open(noise_bank_path, 'r') as f:
        noise_bank = json.load(f)
    
    target_envs = envs if envs else list(noise_bank.keys())
    
    all_results = []

    for set_name, manifest_path in clean_manifests.items():
        print(f"Processing set: {set_name}...")
        df = pd.read_csv(manifest_path)
        
        # For ACL, only use the verified clean sources for controlled mixing
        if set_name == "acl" and 'is_clean' in df.columns:
            df = df[df['is_clean'] == True]
        
        for _, row in df.iterrows():
            audio_path = row['path']
            text = row.get('text', row.get('transcript', ''))
            
            try:
                clean_audio, sr = load_audio(audio_path)
            except Exception as e:
                print(f"Error reading {audio_path}: {e}")
                continue

            for env in target_envs:
                for snr in snrs:
                    try:
                        # Mix
                        noisy_audio = mixer.mix(clean_audio, env, snr)
                        
                        # Save file
                        stem = Path(audio_path).stem
                        filename = f"{set_name}_{stem}_{env}_{snr}dB.wav"
                        save_path = out_path / filename
                        
                        sf.write(save_path, noisy_audio, sr)
                        
                        all_results.append({
                            "original_path": audio_path,
                            "noisy_path": str(save_path),
                            "text": text,
                            "environment": env,
                            "snr": snr,
                            "set": set_name
                        })
                    except Exception as e:
                        print(f"Error mixing {audio_path} with {env} at {snr}dB: {e}")

    # Save final evaluation manifest
    results_df = pd.DataFrame(all_results)
    results_df.to_csv("eval/manifests/eval_harness_manifest.csv", index=False)
    print(f"Harness complete. Manifest saved to eval/manifests/eval_harness_manifest.csv")

if __name__ == "__main__":
    run_harness()
