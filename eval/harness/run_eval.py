import os
import json
import re
import pandas as pd
import soundfile as sf
import io
import numpy as np
import librosa
from pathlib import Path
from eval.harness.mixer import NoiseMixer

TARGET_SR = 16000  # Consistent sample rate for mixing

# Parquet audio column, most specific name first: Loquacious stores a `wav`
# struct of {bytes, path}. The looser names are kept for other HF exports.
_AUDIO_COLS = ('wav', 'audio', 'bytes', 'data')
_ID_COLS = ('ID', 'id', 'utt_id')


def _safe_stem(value):
    """Filename-safe form of an utterance id (Loquacious ids contain ':')."""
    return re.sub(r'[^A-Za-z0-9._-]', '_', str(value))


def load_audio(path, utt_id=None):
    """Load one utterance, from a wav file or a parquet shard, resampled to TARGET_SR.

    A parquet shard holds thousands of utterances, so `utt_id` selects the row.
    Without it only row 0 is reachable, which silently paired every reference in
    the shard with the first utterance's audio.
    """
    if path.endswith('.parquet'):
        df = pd.read_parquet(path)
        audio_col = next((c for c in _AUDIO_COLS if c in df.columns), None)
        if audio_col is None:
            raise ValueError(f"No audio column found in parquet file {path}")
        if utt_id is None:
            row = df.iloc[0]
        else:
            id_col = next((c for c in _ID_COLS if c in df.columns), None)
            if id_col is None:
                raise ValueError(f"No id column in {path}; cannot select utterance {utt_id}")
            match = df[df[id_col].astype(str) == str(utt_id)]
            if match.empty:
                raise ValueError(f"Utterance {utt_id} not found in {path}")
            row = match.iloc[0]
        audio_bytes = row[audio_col]
        # Handle HuggingFace‑style dicts
        if isinstance(audio_bytes, dict):
            audio_bytes = audio_bytes.get('bytes')
        with io.BytesIO(audio_bytes) as buf:
            audio, sr = sf.read(buf)
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
    envs=None, # If None, use all from noise bank
    limit_per_set=None, # Cap utterances taken from each clean manifest
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
        if not existing_df.empty and 'id' not in existing_df.columns:
            # Manifests written before utterance ids were threaded through name every
            # parquet mix after the shard, not the utterance, so their references do
            # not match their audio. Resuming would carry that corruption forward.
            raise RuntimeError(
                f"{manifest_path} predates the utterance-id fix and its rows are "
                "mismatched. Delete it (and the stale mixes in "
                f"{output_dir}) and re-run the harness."
            )
        # Resume on the output filename: it is unique per (utterance, env, snr).
        processed = set(existing_df['noisy_path']) if not existing_df.empty else set()
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
        if limit_per_set:
            df = df.head(limit_per_set)
        for _, row in df.iterrows():
            audio_path = row['path']
            utt_id = row.get('id', None)
            if pd.isna(utt_id):
                utt_id = None
            text = row.get('text', row.get('transcript', ''))
            if pd.isna(text):
                text = ''
            # Name by utterance, not by container: one parquet shard holds thousands.
            stem = _safe_stem(utt_id) if utt_id is not None else Path(audio_path).stem
            combos = []
            for env in target_envs:
                for snr in snrs:
                    save_path = out_path / f"{set_name}_{stem}_{env}_{snr}dB.wav"
                    if str(save_path) not in processed:
                        combos.append((env, snr, save_path))
            if not combos:
                continue
            try:
                clean_audio, sr = load_audio(audio_path, utt_id)
            except Exception as e:
                print(f"\n  Error reading {audio_path} ({utt_id}): {e}")
                continue
            for env, snr, save_path in combos:
                try:
                    noisy_audio = mixer.mix(clean_audio, env, snr)
                    sf.write(save_path, noisy_audio, TARGET_SR)
                    all_results.append({
                        "id": utt_id if utt_id is not None else Path(audio_path).stem,
                        "original_path": audio_path,
                        "noisy_path": str(save_path),
                        "text": text,
                        "environment": env,
                        "snr": snr,
                        "set": set_name
                    })
                    processed.add(str(save_path))
                except Exception as e:
                    print(f"\n  Error mixing {audio_path} with {env} at {snr}dB: {e}")

    results_df = pd.DataFrame(all_results)
    results_df.to_csv(manifest_path, index=False)
    print(f"\nHarness complete. Manifest saved to {manifest_path} ({len(results_df)} rows)")

if __name__ == "__main__":
    run_harness()
