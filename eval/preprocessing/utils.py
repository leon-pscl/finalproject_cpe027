import re
import numpy as np
import soundfile as sf
import io

def normalize_text(text):
    if not text: return ''
    text = text.upper()
    text = re.sub(r'\[.*?\]|\(.*?\)', ' ', text)
    text = re.sub(r'[^A-Z0-9\']', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def calculate_rms(audio_data):
    return np.sqrt(np.mean(np.square(audio_data)))

def get_snr_proxy(audio_data, sr=16000):
    if len(audio_data) == 0: return -float('inf')
    abs_audio = np.abs(audio_data)
    peak = np.max(abs_audio)
    if peak == 0: return -float('inf')
    noise_floor = np.median(np.sort(abs_audio)[:int(len(abs_audio)*0.1)])
    if noise_floor == 0: return 100.0
    return 20 * np.log10(peak / noise_floor)
