import os
import json
import soundfile as sf
from pathlib import Path
from .utils import calculate_rms

def prepare_demand(data_root, output_json):
    root = Path(data_root)
    noise_bank = {}
    
    # Find all 16k zips/folders
    for env_dir in root.glob('*_16k'):
        if env_dir.is_dir():
            # Use Channel 01 as the standard
            # Path: E:\Datasets\DEMAND\DKITCHEN_16k\DKITCHEN\ch01.wav
            wav_path = env_dir / env_dir.name.replace('_16k', '') / 'ch01.wav'
            if wav_path.exists():
                audio, sr = sf.read(wav_path)
                noise_bank[env_dir.name.replace('_16k', '')] = {
                    'path': str(wav_path),
                    'rms': calculate_rms(audio),
                    'sr': sr
                }
                
    with open(output_json, 'w') as f:
        json.dump(noise_bank, f, indent=4)

if __name__ == '__main__':
    prepare_demand(r'E:\Datasets\DEMAND', 'eval/manifests/noise_bank.json')
