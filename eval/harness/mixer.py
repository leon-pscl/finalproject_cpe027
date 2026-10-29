import numpy as np
import soundfile as sf
import json
import pandas as pd
from pathlib import Path
import librosa
from ..preprocessing.utils import calculate_rms

class NoiseMixer:
    def __init__(self, noise_bank_path, target_sr=16000):
        with open(noise_bank_path, 'r') as f:
            self.noise_bank = json.load(f)
        # Cache for loaded noise audio (env_name -> (audio, sr))
        self._noise_cache = {}
        self.target_sr = target_sr
    
    def _load_noise(self, env_name):
        """Load and cache noise audio for a given environment, resampling to target_sr if needed."""
        if env_name not in self._noise_cache:
            noise_info = self.noise_bank[env_name]
            noise_path = noise_info['path']
            noise_audio, sr = sf.read(noise_path)
            # Resample to target_sr if necessary
            if sr != self.target_sr:
                # librosa expects mono; if multi‑channel, take mean
                if noise_audio.ndim > 1:
                    noise_audio = np.mean(noise_audio, axis=1)
                noise_audio = librosa.resample(noise_audio, orig_sr=sr, target_sr=self.target_sr)
                sr = self.target_sr
            else:
                # Ensure mono
                if noise_audio.ndim > 1:
                    noise_audio = np.mean(noise_audio, axis=1)
            self._noise_cache[env_name] = (noise_audio, sr)
        return self._noise_cache[env_name]
    
    def mix(self, clean_audio, env_name, target_snr):
        if env_name not in self.noise_bank:
            raise ValueError(f'Environment {env_name} not found in noise bank.')
        # Load (or retrieve cached) noise audio (already at target_sr)
        noise_audio, sr = self._load_noise(env_name)
        
        # Ensure clean_audio matches the same sampling rate
        # (clean_audio should already be at target_sr before calling this)
        
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
