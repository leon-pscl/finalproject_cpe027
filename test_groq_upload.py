import os
import pandas as pd
from backend.app.groq_asr import transcribe_file
from backend.app.config import get_settings

# Ensure settings loaded (reads .env)
settings = get_settings()
api_key = settings.groq_api_key
if not api_key:
    raise RuntimeError("GROQ_API_KEY not set in environment")

# Helper to test a file path
def test_file(path, label):
    print(f"\n=== Testing {label} ===")
    print(f"Path: {path}")
    try:
        transcript = transcribe_file(str(path))
        # Print summary of transcript
        seg_count = len(transcript.segments)
        print(f"Success: returned {seg_count} segment(s)")
        if seg_count:
            print("First segment:", transcript.segments[0].text[:200])
    except Exception as e:
        print(f"Failed: {e.__class__.__name__}: {e}")

# 1. ACL – pick first wav
acl_manifest = pd.read_csv("eval/manifests/acl_manifest.csv")
acl_path = acl_manifest.iloc[0]["path"]
if os.path.exists(acl_path):
    test_file(acl_path, "ACL sample (wav)")
else:
    print("ACL sample path does not exist on this machine.")

# 2. Loquacious – pick first parquet
loq_manifest = pd.read_csv("eval/manifests/loq_manifest.csv")
loq_path = loq_manifest.iloc[0]["path"]
if os.path.exists(loq_path):
    test_file(loq_path, "Loquacious sample (parquet)")
else:
    print("Loquacious sample path does not exist on this machine.")

# 3. Musan – pick first entry (tar archive)
musan_manifest = pd.read_csv("eval/manifests/musan_inventory.csv")
musan_path = musan_inventory = musan_manifest.iloc[0]["path"]
if os.path.exists(musan_path):
    test_file(musan_path, "Musan sample (tar.gz)")
else:
    print("Musan sample path does not exist on this machine.")
