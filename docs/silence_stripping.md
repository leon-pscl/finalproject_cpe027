# Silence Stripping (`dsp.strip_silence`)

## Purpose
Long lecture recordings often contain extended periods of silence, music, or background noise that waste transcription time and increase the chance of hitting provider rate limits.  The `strip_silence` helper removes non‑speech segments while preserving a **mapping** from the stripped audio back to the original timeline.  This enables the downstream ASR system to produce timestamps that correspond to the original recording.

## Methodology
1. **Voice Activity Detection (VAD)** – Uses the existing `detect_speech` routine on a power‑spectrogram derived from the audio.  The VAD mask is a binary array per STFT frame indicating speech presence.
2. **Frame‑to‑Sample Conversion** – The VAD mask is converted to sample‑level intervals based on the STFT hop size (`HOP`).
3. **Padding** – Each detected speech interval is padded by a configurable amount (default **250 ms**) before and after to avoid cutting off the beginnings and endings of words.
4. **Gap Merging** – Gaps shorter than **500 ms** are merged, preventing the creation of many tiny chunks that would increase request overhead.
5. **Offset Map Construction** – For every retained segment we record a tuple:
   `(orig_start_s, orig_end_s, stripped_start_s)`.  `orig_*` are timestamps in the original audio, while `stripped_start_s` is the start time of the segment in the concatenated, stripped audio.
6. **Concatenation** – All padded speech segments are concatenated to produce the final stripped audio array, which is returned together with the offset map.

## Usage
```python
import dsp
audio_np = dsp.load_audio(path)
stripped_audio, offset_map = dsp.strip_silence(
    audio_np,
    sr=dsp.SR,
    padding_ms=250,
    min_gap_ms=500,
)
```
The returned `offset_map` is later consumed by the ASR layer to remap timestamps (see `backend/app/asr.py`).

## Rationale
- **Performance** – By skipping silence, the amount of audio sent to the provider is reduced, saving both request‑seconds and monetary cost.
- **Rate‑Limit Compliance** – Smaller payloads mean more chunks can be sent within the provider’s free‑tier limits without exhausting the daily audio‑seconds quota.
- **Accuracy** – Padding prevents truncating the very start or end of spoken words, which could otherwise degrade transcription quality.
- **Traceability** – The offset map guarantees that downstream consumers (e.g., note generation) can refer back to the original timestamps, preserving synchronization with any existing video or slide decks.

---

*Implemented on 2026‑10‑30 as part of the Groq ASR chunking and rate‑limiting enhancements.*