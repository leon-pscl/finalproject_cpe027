import os
import csv
import pandas as pd
from pathlib import Path
from .utils import normalize_text

def prepare_loquacious(data_root, manifest_path):
    root = Path(data_root)
    # Process dev and test
    splits = ['dev', 'test']
    manifest = []
    
    for split in splits:
        pq_dir = root / split / 'local'
        for pq_file in pq_dir.glob('*.parquet'):
            df = pd.read_parquet(pq_file)
            for _, row in df.iterrows():
                manifest.append({
                    'id': row['ID'],
                    'split': split,
                    'spk_id': row['spk_id'],
                    'text': normalize_text(row['text']),
                    'path': str(pq_file) # Store parquet path, evaluate will seek by ID
                })
                
    with open(manifest_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'split', 'spk_id', 'text', 'path'])
        writer.writeheader()
        writer.writerows(manifest)

if __name__ == '__main__':
    prepare_loquacious(r'E:\Datasets\loquacius', 'eval/manifests/loq_manifest.csv')
