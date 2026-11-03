# Evaluation Pipeline

The evaluation harness lives in `backend/app/eval_runner.py`. It runs entirely from
the existing ASR/DSP pipeline and writes machine-readable JSON, CSV, plus summary
aggregates. Tier 1 and Tier 2 are reported separately and are never averaged
together.

## Data Roots

Set these in `backend/.env`:

```env
EVAL_DATA_ROOT=E:\Datasets
```

Expected extracted inputs:

- ACL6060:
  `E:\Datasets\(ACL6060)2023.iwslt-1.2.dataset\2\acl_6060\{dev,eval}`
- DEMAND:
  `E:\Datasets\DEMAND\{DKITCHEN,DLIVING,DWASHING}_16k\...`
- M3AV (Tier 2):
  an extracted root containing `clip_id/speech/final+timestamps.json`

### M3AV Extraction (prerequisite)

The M3AV audio archive is split into `dataset_v1.0_onlyaudio.tar.gz.00`..`.08`.
Concatenate and extract only the needed subset on Windows:

```powershell
cd E:\Datasets\M3AV\local\dataset_v1.0_onlyaudio_tar_gz
copy /b dataset_v1.0_onlyaudio.tar.gz.* dataset_v1.0_onlyaudio.tar.gz
tar -tzf dataset_v1.0_onlyaudio.tar.gz | Select-String "CHI-17856"
tar -xzf dataset_v1.0_onlyaudio.tar.gz .\dataset_v1.0_onlyaudio\CHI-17856
```

The no-audio archive can be extracted normally:

```powershell
cd E:\Datasets\M3AV\local
tar -xzf dataset_v1.0_noaudio.tar.gz
```

Point the runner at the extracted root with `--m3av-root`.

### DEMAND Extraction

DEMAND folders are shipped as ZIP files. Extract the relevant indoor environments:

```powershell
cd E:\Datasets\DEMAND
Expand-Archive DKITCHEN_16k.zip .
Expand-Archive DLIVING_16k.zip .
Expand-Archive DWASHING_16k.zip .
```

Only `DKITCHEN`, `DLIVING`, and `DWASHING` are used by default. Outdoor
environments (`NFIELD`, `NPARK`, `NRIVER`) are intentionally excluded because
they are not representative of lecture capture conditions.

## Tier 1 - ACL6060

Tier 1 uses ACL6060 talk audio, transcripts, and bracketed technical terms.

Reference parsing:
- `text/xml/ACL.6060.{split}.en-xx.en.xml` supplies per-talk ground truth.
- `text/tagged_terminology/...` supplies bracketed technical terms.

Conditions:
1. `arm_a`: media normalization only (`DSPConfig.bypass=True`)
2. `hp`: high-pass + normalization
3. `hp+sg`: high-pass + spectral gating + normalization

Media processing happens through `app.media`, then ASR runs with `enhance=False`.
This is the production DSP path rather than the `enhance=True` path in
`app.evaluate`.

Noise robustness:
- Clean run plus seeded DEMAND/custom-WAV injection at requested SNRs.
- The random seed is fixed per talk/noise/SNR combination so repeated runs reproduce
  the same noisy inputs and the same noise segment across DSP conditions.
- Signal-level SNR improvement is measured against the unmodified clean talk.

Metrics:
- `wer`
- `cer`
- `kter`: ACL6060 bracketed-term accuracy (renamed from term accuracy; equivalent
  to the `app.evaluate.term_accuracy` result)
- `signal_snr_improvement_db`
- `rtf`
- `seconds`

Outputs:
- `tier1_acl_results.json`
- `tier1_acl_results.csv`
- `tier1_acl_summary.json`

## Tier 2 - M3AV

Tier 2 evaluates unmodified M3AV recordings.

Inputs:
- `speech/final+timestamps.json` supplies reference text, word timestamps, and duration.
- `paper/paper_sentences.json` supplies the heuristic key-term list.
- Audio is discovered under each clip directory.

Conditions are the same as Tier 1. There is no noise injection and no
signal-level SNR improvement metric because there is no clean reference.

Metrics:
- `wer`
- `cer`
- `kter`: heuristic key-term accuracy derived from paper sentences
- `rtf`
- `seconds`
- `nshr`: non-speech hallucination rate

`NSHR` is computed at segment level: an ASR segment is hallucinated if its
timestamp span does not overlap any ground-truth speech interval from
`words_spoken`.

Summaries are grouped by `duration_bucket`:
- `<5m`
- `5-10m`
- `10-20m`
- `>=20m`

A whole-condition summary is also emitted for aggregate behavior.

Outputs:
- `tier2_m3av_results.json`
- `tier2_m3av_results.csv`
- `tier2_m3av_summary.json`

## DNSMOS

DNSMOS is intentionally deferred. The runner records it as deferred rather than
attempting to require an optional model or package that may not be installed.

## Running

From `backend/`:

```powershell
python -m app.eval_runner --tier 1 --split eval --conditions arm_a,hp,hp+sg --snrs none,0,5,10,20 --noise demand --demand-envs DKITCHEN,DLIVING,DWASHING --out ..\eval_results
```

```powershell
python -m app.eval_runner --tier 2 --m3av-root "E:\Datasets\M3AV\extracted" --conditions arm_a,hp,hp+sg --out ..\eval_results
```

```powershell
python -m app.eval_runner --tier all --limit 1 --out ..\eval_smoke
```

## Language Handling for ACL Tier 1

ACL6060 is an English-only dataset. With `WHISPER_LANGUAGE=` left empty,
faster-whisper uses automatic language detection, which may select the wrong
language for long recordings and inflate WER even when the transcript is partly
correct. Force English for Tier 1 evaluation:

```powershell
$env:WHISPER_LANGUAGE="en"
python -m app.eval_runner --tier 1 --split eval ...
```

This override applies only to the evaluation command/session. Production keeps
`WHISPER_LANGUAGE=` empty so the ASR stage can auto-detect Filipino/English
code-switching.

## Sample Size

Tier 1 reports five eval talks. Standard deviations are reported for every
aggregate, but no statistical significance is claimed from those values. Tier 2
reports duration-bucket aggregates separately from the full condition aggregate;
tiers themselves are never pooled or averaged.