import numpy as np
import soundfile as sf
import json
import pandas as pd
from pathlib import Path
from eval.preprocessing.utils import calculate_rms

class NoiseMixer:
    def __init__(self, noise_bank_path):
        with open(noise_bank_path, 'r') as f:
            self.noise_bank = json.load(f)
    
    def mix(self, clean_audio, env_name, target_snr):
        if env_name not in self.noise_bank:
            raise ValueError(f'Environment {env_name} not found in noise bank.')
        
        noise_info = self.noise_bank[env_name]
        noise_audio, sr = sf.read(noise_info['path'])
        
        # Ensure noise is long enough for the signal
        if len(noise_audio) < len(clean_audio):
            tile_count = (len(clean_audio) // len(noise_audio)) + 1
            noise_audio = np.tile(noise_audio, tile_count)[:len(clean_audio)]
        else:
            start = np.random.randint(0, len(noise_audio) - len(clean_audio) + 1)
            noise_audio = noise_audio[start : start + len(clean_audio)]
        
        sig_rms = calculate_rms(clean_audio)
        target_noise_rms = sig_rms / (10 ** (target_snr / 20))
        
        current_noise_rms = calculate_rms(noise_audio)
        if current_noise_rms == 0:
            return clean_audio
            
        scaling_factor = target_noise_rms / current_noise_rms
        mixed_audio = clean_audio + (noise_audio * scaling_factor)
        
        # Normalize to prevent clipping
        max_val = np.max(np.abs(mixed_audio))
        if max_val > 1.0:
            mixed_audio /= max_val
            
        return mixed_audio
