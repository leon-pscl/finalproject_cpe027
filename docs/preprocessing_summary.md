# Preprocessing Summary: Datasets & Pipelines

This document archives the preprocessing steps taken to prepare the datasets for the ASR evaluation harness.

## 🎯 Objectives
- Create a clean, normalized baseline for evaluation.
- Establish a controlled noise-mixing pipeline using the DEMAND dataset.
- Implement a manifest-first approach to avoid redundant audio copying.

## 🛠 Dataset Processing

### 1. ACL 60/60
- **Scope**: English development set.
- **Screening**: Implemented a "Tier 1" screening process using an SNR proxy (Peak vs. 10% lowest samples).
- **Threshold**: Samples with an SNR proxy > 20dB were marked as `is_clean=True`.
- **Outcome**: Generated `eval/manifests/acl_manifest.csv` containing IDs, paths, and cleanliness flags.

### 2. LoquaciousSet
- **Source**: Data stored in Parquet files (audio bytes + text).
- **Normalization**: Applied the **"Loquacious Standard"**:
    - Forced UPPERCASE.
    - Removed punctuation (except apostrophes).
    - Numerals converted to words.
- **Outcome**: Generated `eval/manifests/loq_manifest.csv` with normalized references and paths to the original Parquet shards.

### 3. DEMAND (Noise Bank)
- **Channel Selection**: Fixed use of `ch01.wav` for all environments for consistency across tests.
- **Indexing**: Calculated and stored the RMS values for all environment files.
- **Outcome**: Generated `eval/manifests/noise_bank.json` as a lookup table for the `NoiseMixer`.

## 🔄 The Mixing Pipeline
The `eval/harness/mixer.py` tool implements the following logic:
1. **Signal-to-Noise Calculation**: $SNR = 20 \cdot \log_{10}(\frac{RMS_{signal}}{RMS_{noise}})$.
2. **Noise Adaptation**: Noise is either randomly cropped or tiled to match the length of the clean signal.
3. **Scaling**: Noise is scaled to achieve the target SNR.
4. **Normalization**: Peak normalization is applied to prevent clipping after mixing.

## 📂 Final Manifests
| Manifest | Description |
| :--- | :--- |
| `acl_manifest.csv` | Verified sources for ACL 60/60. |
| `loq_manifest.csv` | Normalized references for LoquaciousSet. |
| `noise_bank.json` | RMS values and paths for DEMAND noise. |
| `eval_harness_manifest.csv` | Final mapping of `Original` $\rightarrow$ `Noisy` $\rightarrow$ `Ground Truth`. |
