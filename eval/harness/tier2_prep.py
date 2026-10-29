import pandas as pd
from pathlib import Path

def generate_tier2_manifest(
    acl_manifest_path="eval/manifests/acl_manifest.csv",
    output_manifest_path="eval/manifests/tier2_manifest.csv"
):
    """
    Extracts real-world noisy samples from the ACL manifest (where is_clean is False)
    and formats them to match the evaluation harness schema.
    """
    print(f"Generating Tier 2 manifest from {acl_manifest_path}...")
    
    df = pd.read_csv(acl_manifest_path)
    
    if 'is_clean' not in df.columns:
        raise KeyError("ACL manifest must contain 'is_clean' column for Tier 2 extraction.")
    
    # Filter for samples that are NOT clean (Real noisy recordings)
    tier2_df = df[df['is_clean'] == False].copy()
    
    # Map to the evaluation harness schema:
    # original_path, noisy_path, text, environment, snr, set
    # For Tier 2, original_path and noisy_path are the same (the recording is already noisy)
    # Environment is 'REAL', SNR is 'Unknown'
    
    tier2_final = pd.DataFrame({
        "original_path": tier2_df['path'],
        "noisy_path": tier2_df['path'],
        "text": tier2_df['text'] if 'text' in tier2_df.columns else "",
        "environment": "REAL",
        "snr": "Unknown",
        "set": "acl_real"
    })
    
    tier2_final.to_csv(output_manifest_path, index=False)
    print(f"Tier 2 manifest saved to {output_manifest_path}. Total samples: {len(tier2_final)}")
    return tier2_final

if __name__ == "__main__":
    generate_tier2_manifest()
