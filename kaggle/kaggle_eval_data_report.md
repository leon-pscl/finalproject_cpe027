# Kaggle Evaluation Data Report — finalproject_cpe027

Local verification of the preprocessed evaluation data feeding the Kaggle ASR run
(`backend/app/eval_runner.py`, helpers in `backend/app/eval_data.py`).

Verified against local data root: `E:\Datasets` (`EVAL_DATA_ROOT`).

## ACL6060 (Tier 1)

- Dataset root: `E:\Datasets\(ACL6060)2023.iwslt-1.2.dataset\2\acl_6060`
- Consumed layout: `<root>/{dev,eval}/{full_wavs,text/xml,text/tagged_terminology}`
- Findings:
  - `eval/full_wavs`: **5 talks** — `2022.acl-long.111.wav`, `2022.acl-long.410.wav`,
    `2022.acl-long.468.wav`, `2022.acl-long.567.wav`, `2022.acl-long.597.wav` (~11.5 min each,
    ~70 min total clean speech).
  - `dev/full_wavs`: 5 talks (same pattern).
  - Only `ACL.6060.<split>.en-xx.en.xml` and `ACL.6060.<split>.tagged.en-xx.en.txt` are read;
    other languages are excluded.
  - Not needed: `segmented_wavs/`, `intermediate_files/`, `FILE_ORDER`, `.DS_Store`.

## DEMAND (Tier 1 noise)

- Used envs: `DKITCHEN_16k`, `DLIVING_16k`, `DWASHING_16k` (16 kHz). Other envs excluded.
- Shape: `DEMAND/<ENV>_16k/<ENV>/*.wav` (16 wavs per env, ~150 MB each).

## M3AV (Tier 2)

- Root: `E:\Datasets\M3AV\local\dataset_v1.0_noaudio`
- Clips: **1113** clip dirs, each with `speech/final+timestamps.json` + `audio.flac`;
  **43.5 GB** FLAC total (~39 MB/clip).
- Local Tier 2 state: smoke only — `CHI-003EC`, conditions `arm_a,hp`; full run pending.

## Flags / caveats

- `hp_wiener_oa`: DSP code notes the observed-audio blend is not fully implemented; the
  condition may degrade to plain `hp_wiener`.
- Tier 1 sample size: n=5 eval talks; no significance claimed.

## Kaggle packaging — contents-at-root

### acl6060.zip
Entries (NO wrapper folder):
```
dev/full_wavs/*.wav
dev/text/xml/ACL.6060.dev.en-xx.en.xml
dev/text/tagged_terminology/ACL.6060.dev.tagged.en-xx.en.txt
eval/full_wavs/*.wav
eval/text/xml/ACL.6060.eval.en-xx.en.xml
eval/text/tagged_terminology/ACL.6060.eval.tagged.en-xx.en.txt
```
Excluded: `segmented_wavs/`, `intermediate_files/`, `FILE_ORDER`, `.DS_Store`, non-English XML/tagged files.

### demand.zip
```
DEMAND/DKITCHEN_16k/...  (wavs)
DEMAND/DLIVING_16k/...
DEMAND/DWASHING_16k/...
```

### m3av.zip (single archive ~40 GB → split by clip range)
```
M3AV/extracted/<clip_id>/speech/final+timestamps.json
M3AV/extracted/<clip_id>/audio.flac
```

## Staging + zip commands (PowerShell, staging under E:\Datasets)

```powershell
# ACL6060 — contents-at-root
$stage = "E:\Datasets\kaggle_stage\acl6060"
Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force "$stage\dev\full_wavs","$stage\eval\full_wavs","$stage\dev\text\xml","$stage\dev\text\tagged_terminology","$stage\eval\text\xml","$stage\eval\text\tagged_terminology" | Out-Null
Copy-Item "E:\Datasets\(ACL6060)2023.iwslt-1.2.dataset\2\acl_6060\dev\full_wavs\*.wav" "$stage\dev\full_wavs\"
Copy-Item "E:\Datasets\(ACL6060)2023.iwslt-1.2.dataset\2\acl_6060\eval\full_wavs\*.wav" "$stage\eval\full_wavs\"
Copy-Item "E:\Datasets\(ACL6060)2023.iwslt-1.2.dataset\2\acl_6060\dev\text\xml\ACL.6060.dev.en-xx.en.xml" "$stage\dev\text\xml\"
Copy-Item "E:\Datasets\(ACL6060)2023.iwslt-1.2.dataset\2\acl_6060\dev\text\tagged_terminology\ACL.6060.dev.tagged.en-xx.en.txt" "$stage\dev\text\tagged_terminology\"
Copy-Item "E:\Datasets\(ACL6060)2023.iwslt-1.2.dataset\2\acl_6060\eval\text\xml\ACL.6060.eval.en-xx.en.xml" "$stage\eval\text\xml\"
Copy-Item "E:\Datasets\(ACL6060)2023.iwslt-1.2.dataset\2\acl_6060\eval\text\tagged_terminology\ACL.6060.eval.tagged.en-xx.en.txt" "$stage\eval\text\tagged_terminology\"
Compress-Archive -Path "$stage\*" -DestinationPath "E:\Datasets\acl6060.zip" -Force

# DEMAND
Compress-Archive -Path "E:\Datasets\DEMAND\DKITCHEN_16k","E:\Datasets\DEMAND\DLIVING_16k","E:\Datasets\DEMAND\DWASHING_16k" -DestinationPath "E:\Datasets\demand.zip" -Force

# M3AV — split by clip range first (see runbook), then Compress-Archive with M3AV/extracted/<clip_id>/ layout.
```

## Kaggle dataset create/upload commands (private)

Each dataset folder contains the zip + `dataset-metadata.json`, e.g.:

```json
{
  "title": "finalproject_cpe027-eval-acl6060",
  "id": "leon-pscl/finalproject_cpe027-eval-acl6060",
  "subtitle": "ACL6060 eval inputs for Kaggle ASR eval",
  "description": "ACL6060 dev/eval full_wavs + en-xx.en transcripts for Tier 1 evaluation.",
  "licenses": [{ "name": "MIT" }]
}
```

```bash
kaggle datasets create --private -p /path/to/acl6060_dataset
kaggle datasets create --private -p /path/to/demand_dataset
kaggle datasets create --private -p /path/to/m3av_dataset_split_a   # first clip range
kaggle datasets create --private -p /path/to/m3av_dataset_split_b   # second clip range
```

Upload alternative: `kaggle datasets upload /path/to/acl6060_dataset`.
