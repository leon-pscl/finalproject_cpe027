#!/usr/bin/env python
"""
Demo script: runs the full pipeline on audio files placed in the `samples/` folder.
It demonstrates:
- DSP cleaning (if DSP_ENABLED=true in .env)
- ASR transcription via faster‑whisper
- Chunking, embedding and FAISS indexing
- RAG note generation
- Optional evaluation using the built‑in evaluate module (requires a matching .txt reference file)
The script runs without a FastAPI server – it builds the in‑memory repository,
storage adapter and worker directly.
"""

import os
import sys
import time
import uuid
import json
import pathlib
import subprocess

# Ensure the project root is on the import path
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from backend.app.config import get_settings
from backend.app.dependencies import get_repository, get_storage
from backend.app.jobs import JobStore
from backend.app.worker import PipelineWorker
from backend.app.adapters import adapter_bundle
from backend.app.storage import LocalStorageAdapter
from backend.app.repositories import InMemoryLectureRepository
from backend.app.contracts import Chunk


def main() -> None:
    settings = get_settings()
    storage_root = settings.local_storage_root
    storage = LocalStorageAdapter(get_settings())
    repo = InMemoryLectureRepository()
    store = JobStore()
    worker = PipelineWorker(repo, storage, settings)

    samples_dir = ROOT / "samples"
    if not samples_dir.is_dir():
        print("[demo] No 'samples' directory found.")
        sys.exit(1)

    audio_files = [p for p in samples_dir.iterdir() if p.suffix.lower() in {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}]
    if not audio_files:
        print("[demo] No audio files in 'samples' folder.")
        return

    user_id = "demo_user"
    for audio_path in audio_files:
        lecture_id = f"lec-{uuid.uuid4().hex[:8]}"
        title = f"Demo lecture {audio_path.name}"
        # Build storage path for raw file
        raw_storage_path = f"users/{user_id}/{lecture_id}/raw{audio_path.suffix.lower()}"
        # Register lecture metadata
        repo.create_lecture(
            owner_id=user_id,
            lecture_id=lecture_id,
            title=title,
            storage_path=raw_storage_path,
            declared_type=f"audio/{audio_path.suffix.lstrip('.').lower()}",
            declared_size_bytes=audio_path.stat().st_size,
        )
        # Store raw audio
        with open(audio_path, "rb") as f:
            raw_data = f.read()
        storage.save_object(raw_storage_path, raw_data, f"audio/{audio_path.suffix.lstrip('.').lower()}")

        # Submit a processing job (enhance flag follows DSP_ENABLED)
        job = store.submit(str(audio_path), enhance=settings.dsp_enabled)
        print(f"[demo] Submitted job {job.id} for {audio_path.name}")

        # Process until the job reaches a terminal state
        while True:
            worker.run_once()
            refreshed = store.get(job.id)
            if refreshed is None or refreshed.state in {"completed", "failed"}:
                job = refreshed
                break
            time.sleep(0.5)

        if job is None or job.state != "completed":
            print(f"[demo] Job {job.id} failed or was not completed.")
            continue

        # Load and display a snippet of the transcript
        transcript_bytes, _ = storage.read_object(f"users/{user_id}/{lecture_id}/transcript.json")
        transcript = json.loads(transcript_bytes.decode())
        first_seg = transcript.get("segments", [{}])[0].get("text", "")
        print(f"[demo] Transcript start: {first_seg[:80]}…")

        # Generate notes via the RAG pipeline
        chunks_bytes, _ = storage.read_object(f"users/{user_id}/{lecture_id}/chunks.json")
        chunks_data = json.loads(chunks_bytes.decode())
        chunks = [Chunk(**c) for c in chunks_data]
        notes_gen = adapter_bundle()["notes"]
        notes = notes_gen.generate(chunks, {"lecture_id": lecture_id, "processing_version": "v1"})
        print(f"[demo] Generated {len(notes)} notes for {audio_path.name} (showing up to 3):")
        for n in notes[:3]:
            print(f"  • {n.title}: {n.body[:60].replace('\n', ' ')}…")

        # Optional evaluation if a reference transcript exists (same stem with .txt)
        reference_path = audio_path.with_suffix('.txt')
        if reference_path.is_file():
            eval_out = ROOT / "samples" / "eval_results" / lecture_id
            eval_out.mkdir(parents=True, exist_ok=True)
            cmd = [
                sys.executable,
                "-m",
                "app.evaluate",
                "--audio", str(audio_path),
                "--reference", str(reference_path),
                "--out", str(eval_out),
            ]
            print(f"[demo] Running evaluation for {audio_path.name} → {eval_out}")
            subprocess.run(cmd, check=True)
        else:
            print(f"[demo] No reference .txt found for {audio_path.name}; skipping evaluation.")

    print("[demo] All samples processed.")


if __name__ == "__main__":
    main()
