"""Extract M3AV FLAC audio directly into the annotation clip directories.

This avoids creating a second 10+ GB copy of every clip. It reads the split
tar/gzip archive as a stream and writes each matching FLAC into:
    <m3av-root>/<clip_id>/audio.flac
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import sys
import tarfile
from pathlib import Path

DEFAULT_PARTS_PATTERN = "dataset_v1.0_onlyaudio.tar.gz.*"
NOAUDIO_NAME = "dataset_v1.0_noaudio"


class ConcatenatedReader:
    """Read multiple files sequentially with a single file-like object."""

    def __init__(self, paths: list[Path]) -> None:
        self._paths = paths
        self._index = 0
        self._current = None
        self._open_next()

    def _open_next(self) -> None:
        while self._index < len(self._paths):
            path = self._paths[self._index]
            self._index += 1
            try:
                fh = path.open("rb")
            except OSError:
                continue
            self._current = fh
            return
        self._current = None

    def read(self, size: int = -1) -> bytes:
        if self._current is None:
            return b""
        if size is None or size < 0:
            size = 1024 * 1024
        parts: list[bytes] = []
        remaining = size
        while remaining > 0 and self._current is not None:
            chunk = self._current.read(remaining)
            if not chunk:
                try:
                    self._current.close()
                except OSError:
                    pass
                self._open_next()
                continue
            parts.append(chunk)
            remaining -= len(chunk)
        return b"".join(parts)

    def close(self) -> None:
        if self._current is not None:
            try:
                self._current.close()
            except OSError:
                pass
            self._current = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--m3av-root",
        default=r"E:\Datasets\M3AV\local\dataset_v1.0_noaudio",
        help="Extracted M3AV no-audio root.",
    )
    parser.add_argument(
        "--parts-glob",
        default=rf"E:\Datasets\M3AV\local\dataset_v1.0_onlyaudio_tar_gz\{DEFAULT_PARTS_PATTERN}",
        help="Glob matching concatenated archive parts.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace clips that already have audio.flac.",
    )
    return parser.parse_args()


def is_existing_audio(path: Path) -> bool:
    return any(
        (path / name).is_file()
        for name in ("audio.flac", "audio.wav", "audio.mp4", "audio.m4a", "audio.mkv")
    )


def safe_member_name(name: str) -> str:
    # Normalize "./" and backslash forms, keeping only the file basename.
    return os.path.basename(name.replace("\\", "/"))


def main() -> int:
    args = parse_args()
    noaudio_root = Path(args.m3av_root).expanduser()
    if not noaudio_root.is_dir():
        raise SystemExit(f"Missing M3AV root: {noaudio_root}")

    clip_dirs = [
        path
        for path in noaudio_root.iterdir()
        if path.is_dir() and (path / "speech" / "final+timestamps.json").is_file()
    ]
    clips_with_annotations = len(clip_dirs)

    parts = sorted(Path(p) for p in __import__("glob").glob(args.parts_glob))
    if not parts:
        raise SystemExit(f"No archive parts found: {args.parts_glob}")

    print(f"Reading {len(parts)} archive parts", flush=True)
    print(f"Annotation clips found: {clips_with_annotations}", flush=True)

    existing_count = sum(1 for clip in clip_dirs if is_existing_audio(clip))
    print(f"Clips already having audio: {existing_count}", flush=True)

    reader = ConcatenatedReader(parts)
    copied = 0
    skipped = 0
    skipped_missing = 0
    skipped_existing = 0

    try:
        with tarfile.open(fileobj=reader, mode="r|gz") as archive:
            for member in archive:
                member_name = safe_member_name(member.name)
                suffix = Path(member_name).suffix.lower()
                if suffix != ".flac":
                    continue

                clip_id = Path(member_name).stem
                clip_root = noaudio_root / clip_id
                annotation = clip_root / "speech" / "final+timestamps.json"
                target = clip_root / "audio.flac"

                if not annotation.is_file():
                    # Skip audio for clips that are not part of the annotation set.
                    continue

                if target.is_file() and not args.overwrite:
                    skipped_existing += 1
                    continue

                source = archive.extractfile(member)
                if source is None:
                    skipped += 1
                    print(f"WARNING: could not read {member.name}", flush=True)
                    continue

                temp = target.with_name(f".{target.name}.tmp")
                clip_root.mkdir(parents=True, exist_ok=True)
                try:
                    with temp.open("wb") as output:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
                    os.replace(temp, target)
                except Exception as exc:
                    try:
                        temp.unlink(missing_ok=True)
                    except OSError:
                        pass
                    raise SystemExit(f"Failed writing {target}: {exc}") from exc

                copied += 1
                if copied == 1 or copied % 100 == 0 or clip_id == clip_dirs[-1].name:
                    print(f"Extracted {copied} / {clips_with_annotations} FLAC files", flush=True)

    finally:
        reader.close()

    print("")
    print(f"Newly extracted: {copied}")
    print(f"Skipped existing: {skipped_existing}")
    print(f"Skipped unreadable: {skipped}")
    print(f"Skipped missing annotation: {skipped_missing}")

    with_audio = sum(1 for clip in clip_dirs if is_existing_audio(clip))
    print(f"Total clips with audio now: {with_audio} / {clips_with_annotations}")
    if with_audio < clips_with_annotations:
        raise SystemExit("Extraction incomplete")

    print("M3AV audio extraction complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY