# Kaggle evaluation data — zip packaging and extraction

How the local preprocessed evaluation data was packaged into zips, uploaded as Kaggle
datasets, and extracted again inside `kaggle/kaggle_eval.ipynb`.

Related: [`../kaggle/kaggle_eval_runbook.md`](../kaggle/kaggle_eval_runbook.md) (run procedure),
[`evaluation.md`](evaluation.md) (metric definitions).

## Why zips

Kaggle's `/kaggle/working` is capped at ~20 GB and a session at 12 h, so:

- Raw inputs are uploaded as **one zip per dataset** and mounted read-only under
  `/kaggle/input/...` (unmodified).
- The notebook **extracts on demand** into `/kaggle/working/mounts/<label>` only when a
  raw layout is not already mounted, and **deletes each M3AV split right after its run**
  so only one split (~0.7–15.4 GB) is ever expanded at a time.

## Sources (local)

| Dataset | Local source | Carried into zip |
|---|---|---|
| ACL6060 | `E:\Datasets\(ACL6060)2023.iwslt-1.2.dataset\2\acl_6060` | `dev/` + `eval/` `full_wavs/*.wav`, `text/xml/ACL.6060.<split>.en-xx.en.xml`, `text/tagged_terminology/ACL.6060.<split>.tagged.en-xx.en.txt` |
| DEMAND | `E:\Datasets\DEMAND` | `DKITCHEN_16k`, `DLIVING_16k`, `DWASHING_16k` (16 kHz, 16 wavs each) |
| M3AV | `E:\Datasets\M3AV\local\dataset_v1.0_noaudio` (1113 clip dirs) | per clip: `speech/final+timestamps.json` + `audio.flac` |

Excluded everywhere: `segmented_wavs/`, `intermediate_files/`, `FILE_ORDER`, `.DS_Store`,
non-English ACL transcripts, video/preprocessing extras.

## Zip creation

### acl6060.zip (~170 MB)

Stage the six directories listed above, then `Compress-Archive` with **contents at root**
(no wrapper folder). `E:\Datasets\kaggle_stage\kaggle_stage` script:
`C:\Users\Leon\AppData\Local\Temp\opencode\build_kaggle_zips.ps1`.

```
dev/full_wavs/*.wav
dev/text/xml/ACL.6060.dev.en-xx.en.xml
dev/text/tagged_terminology/ACL.6060.dev.tagged.en-xx.en.txt
eval/full_wavs/*.wav
eval/text/xml/ACL.6060.eval.en-xx.en.xml
eval/text/tagged_terminology/ACL.6060.eval.tagged.en-xx.en.txt
```

### demand.zip (~279 MB)

```
DEMAND/DKITCHEN_16k/...
DEMAND/DLIVING_16k/...
DEMAND/DWASHING_16k/...
```

### M3AV splits — `m3av_0.zip` … `m3av_7.zip` (0.68–15.4 GB each)

Source: `E:\Datasets\M3AV\local\dataset_v1.0_noaudio` (1113 clip dirs).
Script: `C:\Users\Leon\AppData\Local\Temp\opencode\build_m3av_zips.py` (or the chunked
PowerShell variant).

Partition: **lexicographic clip-ID order, fixed chunks of 150**.

```python
SRC = r"E:\Datasets\M3AV\local\dataset_v1.0_noaudio"
CLIP_SIZE = 150

clips = sorted(d for d in os.listdir(SRC) if os.path.isdir(os.path.join(SRC, d)))
# 1113 clip dirs
for i in range(0, len(clips), CLIP_SIZE):          # 8 chunks
    tag = str(i // CLIP_SIZE)                     # 0..7
    chunk = clips[i : i + CLIP_SIZE]              # 150 clips; last chunk has 63
    stage = os.path.join("E:/Datasets/kaggle_stage", f"m3av_{tag}")
    for clip_id in chunk:
        # stage/M3AV/extracted/<clip_id>/speech/final+timestamps.json
        # stage/M3AV/extracted/<clip_id>/audio.flac
    ...
```

- 1113 clips → **8 splits** (`m3av_0` … `m3av_7`).
- Range: `m3av_0` = clips 0–149 (`CHI-003EC` …), `m3av_7` = 1050–1112
  (`Ubi-5F667` … `Ubi-FE1DB`).
- Only two files per clip are carried: `speech/final+timestamps.json` + `audio.flac`
  (no video / preprocessing extras).
- Zip layout (contents at root, no wrapper folder):

```
M3AV/extracted/<clip_id>/speech/final+timestamps.json
M3AV/extracted/<clip_id>/audio.flac
```

- Zip sizes: 0.68–15.4 GB, all under Kaggle's 20 GB per-dataset limit.

## Upload

Each zip sits in `E:\Datasets\kaggle_datasets\<name>\` with a `dataset-metadata.json`
(owner `leonpascual1`, MIT license), created privately (slugs hyphenated, no
underscores):

```
kaggle datasets create -p E:\Datasets\kaggle_datasets\acl6060
kaggle datasets create -p E:\Datasets\kaggle_datasets\demand
kaggle datasets create -p E:\Datasets\kaggle_datasets\m3av_0   # … through m3av_7
```

Resulting slugs: `leonpascual1/finalproject-cpe027-eval-{acl6060,demand,m3av-split-0..7}`.

## Extraction inside the notebook

See `kaggle/kaggle_eval.ipynb` cell 1 (data import):

1. **ACL / DEMAND** — matched against the raw mounted layout
   (`dev/full_wavs`, `DKITCHEN_16k`); no extraction needed. If only a zip is attached
   it is expanded once into `/kaggle/working/mounts/<label>` guarded by a `.extracted`
   marker so it never re-extracts on a restarted run.
2. **M3AV** — discovered either as raw roots (`.../M3AV/extracted`) or as
   `*.zip` paths (`M3AV_ZIPS` env var, newline-joined).
3. **Smoke + Tier 2** — one split at a time: extract `m3av_<n>.zip` into
   `/kaggle/working/mounts/m3av_<n>/`, run the bucket batch, then `shutil.rmtree`
   the expanded folder before the next split to stay under 20 GB.

Verification: `python` + `zipfile` over each archive confirmed the entry counts
(e.g. split 0 → 300 entries / 150 clips; split 7 → 126 entries / 63 clips).
