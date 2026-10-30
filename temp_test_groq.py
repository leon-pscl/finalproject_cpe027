import os, json, httpx
from backend.app.config import get_settings, clear_settings_cache
# Force real mode
os.environ['PROCESSING_MODE'] = 'real'
os.environ['ASR_PROVIDER'] = 'groq'
os.environ['WHISPER_MODEL'] = 'whisper-large-v3'
clear_settings_cache()
settings = get_settings()
print('Using model:', settings.whisper_model)
path = 'samples/sent_2.wav'
with open(path, 'rb') as f:
    audio_bytes = f.read()
files = {'file': (os.path.basename(path), audio_bytes, 'application/octet-stream')}
data = {'model': settings.whisper_model, 'response_format': 'json'}
headers = {'Authorization': f"Bearer {settings.groq_api_key}"}
print('Posting request to Groq...')
resp = httpx.post('https://api.groq.com/openai/v1/audio/transcriptions', headers=headers, data=data, files=files, timeout=60.0)
print('Status code:', resp.status_code)
print('Response headers:', resp.headers)
print('Response body (first 500 chars):')
print(resp.text[:500])
