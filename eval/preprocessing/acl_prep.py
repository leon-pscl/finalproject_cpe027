import csv
from pathlib import Path

import soundfile as sf

from .utils import normalize_text, get_snr_proxy


def prepare_acl(data_root, manifest_path, split='dev'):
    """Build the ACL 60/60 manifest from the gold sentence segmentation.

    The dataset ships ``segmented_wavs/gold/sent_N.wav`` aligned one-to-one with line
    N of the English transcript, so the reference text is only recoverable at that
    granularity. The earlier version used ``full_wavs`` (whole 10+ minute talks) and
    never parsed the transcript at all, which left every ACL row with an empty
    reference and a clip far past the benchmark's duration cap.
    """
    root = Path(data_root)
    wav_dir = root / 'acl_6060' / split / 'segmented_wavs' / 'gold'
    text_file = root / 'acl_6060' / split / 'text' / 'txt' / f'ACL.6060.{split}.en-xx.en.txt'

    lines = text_file.read_text(encoding='utf-8').splitlines()
    wav_count = len(list(wav_dir.glob('sent_*.wav')))
    if wav_count != len(lines):
        # sent_N.wav <-> line N is the only thing tying audio to text here; if the
        # counts disagree the mapping is unsafe and every reference would be shifted.
        raise RuntimeError(
            f"ACL {split}: {wav_count} gold wavs but {len(lines)} transcript lines in "
            f"{text_file.name}; refusing to guess the alignment."
        )

    manifest = []
    for n, text in enumerate(lines, start=1):
        wav_path = wav_dir / f'sent_{n}.wav'
        if not wav_path.exists():
            continue
        audio, sr = sf.read(wav_path)
        snr = get_snr_proxy(audio)

        manifest.append({
            'id': f'{split}_sent_{n}',
            'path': str(wav_path),
            'text': normalize_text(text),
            'snr': snr,
            'is_clean': snr > 20  # Tier 1 threshold
        })

    with open(manifest_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'path', 'text', 'snr', 'is_clean'])
        writer.writeheader()
        writer.writerows(manifest)
    print(f"ACL {split}: wrote {len(manifest)} rows to {manifest_path}")


if __name__ == '__main__':
    prepare_acl(r'E:\Datasets\(ACL6060)2023.iwslt-1.2.dataset\2', 'eval/manifests/acl_manifest.csv')
