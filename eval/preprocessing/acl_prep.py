import os
import csv
import soundfile as sf
from pathlib import Path
from .utils import normalize_text, calculate_rms, get_snr_proxy

def prepare_acl(data_root, manifest_path):
    root = Path(data_root)
    # Focused on English dev set as a start
    wav_dir = root / 'acl_6060' / 'dev' / 'full_wavs'
    text_dir = root / 'acl_6060' / 'dev' / 'text' / 'txt'
    
    manifest = []
    for wav_path in wav_dir.glob('*.wav'):
        # Match wav to text file
        text_file = text_dir / f'ACL.6060.dev.en-xx.en.txt' # Simplified: typically one file per set or per talk
        # Note: ACL structure usually has one text file for all talks in a split.
        # We'd need to parse that file to match IDs.
        
        audio, sr = sf.read(wav_path)
        snr = get_snr_proxy(audio)
        
        manifest.append({
            'id': wav_path.stem,
            'path': str(wav_path),
            'snr': snr,
            'is_clean': snr > 20 # Tier 1 threshold
        })
    
    with open(manifest_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'path', 'snr', 'is_clean'])
        writer.writeheader()
        writer.writerows(manifest)

if __name__ == '__main__':
    prepare_acl(r'E:\Datasets\(ACL6060)2023.iwslt-1.2.dataset\2', 'eval/manifests/acl_manifest.csv')
