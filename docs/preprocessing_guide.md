# Preprocessing Pipeline Documentation

## Overview
This document tracks the design, implementation, and refinement of the data preprocessing pipeline for the evaluation harness.

## Pipeline Architecture
The pipeline uses a **Manifest-First** approach. Instead of copying large audio files, we generate metadata manifests that point to original files in E:\Datasets while recording the exact segments, channels, and normalized text to be used.

### Dataset-Specific Pipelines
1. **ACL 60/60 (acl_prep.py)**: 
   - Maps human-edited transcripts to full-length WAVs.
   - Screens for Clean segments based on RMS/Noise floor.
   - Output: eval/manifests/acl_manifest.csv
2. **LoquaciousSet (loq_prep.py)**: 
   - Extracts metadata from Parquet files.
   - Applies aggressive text normalization (Uppercase, No Punc, Num-to-Words).
   - Output: eval/manifests/loq_manifest.csv
3. **DEMAND (demand_prep.py)**: 
   - Indexes environments and selects a fixed channel (Channel 01).
   - Pre-calculates RMS for precise SNR mixing.
   - Output: eval/manifests/noise_bank.json

## Normalization Rules
To ensure consistent WER/CER measurements across mixed-source datasets, the following normalization policy is applied to both references and hypotheses:

### 1. Case & Punctuation
- **Case**: All text converted to UPPERCASE.
- **Punctuation**: All non-alphanumeric characters removed, except for the apostrophe (').
- **Whitespace**: Multiple spaces collapsed into a single space; leading/trailing whitespace trimmed.

### 2. Numerals (The Loquacious Standard)
Since LoquaciousSet uses spelled-out numbers, all datasets will follow this:
- **Integers**: Converted to words (e.g., 2023 -> TWO THOUSAND TWENTY THREE).
- **Decimals**: Converted to words (e.g., 1.5 -> ONE POINT FIVE).
- **Symbols**: Currency/Percentage symbols converted to words (e.g., $ -> DOLLARS, % -> PERCENT).

### 3. Special Tags
- **Non-Speech Tags**: Tags like [applause], [noise], or (laughs) are removed.

## Version History
- 2026-10-29: Initial scaffolding created.
- 2026-10-29: Normalization rules defined (Case, Punctuation, Numerals).
