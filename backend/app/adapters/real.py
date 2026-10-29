"""Real adapter stubs.

In safe local mode these raise immediately when invoked. They are only selected
when ``PROCESSING_MODE=real`` and the relevant provider is configured.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.adapters.base import (
    AnswerGenerator,
    AudioProcessor,
    Chunker,
    Embedder,
    MediaService,
    NotesGenerator,
    Retriever,
    Transcriber,
)
# Ensure `langchain` is installed (e.g., `pip install langchain`).
from app.chunker import Chunker as ChunkerImpl
from app.embedder import Embedder as EmbedderImpl
from app.asr import Transcript


from app.config import get_settings

class AdapterNotConfigured(RuntimeError):
    """Raised when a real adapter is selected but its provider is not configured."""
    pass


def _require_real_mode(name: str) -> None:
    settings = get_settings()
    if settings.processing_mode != "real":
        raise AdapterNotConfigured(f"{name} requires PROCESSING_MODE=real")
    raise AdapterNotConfigured(
        f"{name} is selected in real mode but no provider implementation is "
        "configured in this build; implement the provider adapter first."
    )




class RealMediaService(MediaService):
    def validate_and_extract(self, lecture_id: str, processing_version: str) -> dict:
        _require_real_mode("RealMediaService")
        return {}


class RealAudioProcessor(AudioProcessor):
    def process(self, audio_asset: Any, config: dict) -> Any:
        _require_real_mode("RealAudioProcessor")


class RealTranscriber(Transcriber):
    def transcribe(self, audio_asset: Any, config: dict) -> list[Any]:
        _require_real_mode("RealTranscriber")
        return []


class RealChunker(Chunker):
    def chunk(self, timed_segments: Sequence[Any], config: dict) -> list[Any]:
        """Delegate to concrete Chunker implementation.

        `timed_segments` are the ASR Segment objects. We build a Transcript and
        invoke the shared Chunker, which respects config settings for chunk size
        and overlap.
        """
        # Compute total duration from segment end times.
        duration = max((seg.end for seg in timed_segments), default=0.0)
        # Build a Transcript compatible with the Chunker implementation.
        transcript = Transcript(language="en", duration=duration, segments=list(timed_segments))
        chunker = ChunkerImpl()
        return chunker.chunk(
            transcript,
            config.get("lecture_id", ""),
            config.get("version", ""),
        )



class RealEmbedder(Embedder):
    def embed(self, texts: Sequence[str], config: dict) -> list[list[float]]:
        # `texts` corresponds to the chunk texts. We'll construct dummy Chunk
        # objects just to satisfy the shared Embedder implementation, which expects
        # a list of `Chunk` instances with a `text` attribute.
        from ..contracts import Chunk as ChunkModel
        dummy_chunks = [ChunkModel(chunk_id="tmp", lecture_id=config.get("lecture_id", ""), version=config.get("version", ""), segment_ids=[], start_s=0.0, end_s=0.0, text=t, embedding_model="", embedding_revision="") for t in texts]
        embedder = EmbedderImpl()
        return embedder.embed(dummy_chunks)



from __future__ import annotations

import json
from typing import List

from app.adapters.base import Retriever
from app.adapters.base import Embedder
from app.adapters.base import Chunker
from app.contracts import Chunk
from app.config import get_settings
from app.vector_store import FAISSVectorStore, faiss
from app.storage import LocalStorageAdapter
# from app.adapters import adapter_bundle  # removed to avoid circular import

class RealRetriever(Retriever):
    """LangChain‑compatible retriever.

    It embeds the query using the configured embedder, loads the FAISS index for the
    lecture, and returns a list of ``Chunk`` objects. If the FAISS index is missing
    (e.g. in unit‑test environments), it falls back to reading the stored
    ``chunks.json`` file directly.
    """

    def __init__(self) -> None:
        # Storage is needed only for the fallback path.
        settings = get_settings()
        self._storage = LocalStorageAdapter(settings)
        self._settings = settings

    def _load_vector_store(self, lecture_id: str) -> FAISSVectorStore:
        return FAISSVectorStore(self._settings.local_storage_root, lecture_id)

    def search(
        self, owner_id: str, lecture_id: str, processing_version: str, question: str
    ) -> List[Chunk]:
        # 1️⃣ Embed the query using the shared embedder adapter.
    def search(
        self, owner_id: str, lecture_id: str, processing_version: str, question: str
    ) -> List[Chunk]:
        # 1️⃣ Load the FAISS store; if unavailable, fallback to JSON without embedding.
        vec_store = self._load_vector_store(lecture_id)
        if faiss is None or getattr(vec_store, "index", None) is None:
            # Fallback – read the raw chunks JSON.
            data_bytes, _ = self._storage.read_object(
                f"users/{owner_id}/{lecture_id}/chunks.json"
            )
            chunks_data = json.loads(data_bytes.decode())
            return [Chunk(**c) for c in chunks_data]
+
+        # 2️⃣ Embed the query using the shared embedder adapter (FAISS is available).
+        from app.adapters import adapter_bundle
+        embedder: Embedder = adapter_bundle()["embedder"]
+        # Build a temporary Chunk just to satisfy the embedder's API.
+        tmp = Chunk(
+            chunk_id="tmp",
+            lecture_id=lecture_id,
+            version=processing_version,
+            segment_ids=[],
+            start_s=0.0,
+            end_s=0.0,
+            text=question,
+            embedding_model="tmp",
+            embedding_revision="0",
+        )
+        query_vec = embedder.embed([tmp])[0]
+
+        # 3️⃣ Perform similarity search and return only the chunk objects.
+        results = vec_store.query(query_vec)
+        return [chunk for chunk, _ in results]
*** End Patch
*** End Patch



class RealAnswerGenerator(AnswerGenerator):
    def answer(
        self, question: str, authorized_evidence: Sequence[Any], config: dict
    ) -> Any:
        _require_real_mode("RealAnswerGenerator")


class RealNotesGenerator(NotesGenerator):
    def generate(
        self, authorized_timed_chunks: Sequence[Any], config: dict
    ) -> list[Any]:
        # Summarize lecture using OpenAI LLM. Concatenate chunk texts and ask for a short
        # summary (max ~300 words). This mirrors the mock behavior but produces a real note.
        from app.answer_generator import OpenAIAnswerGenerator

        # Build a simple context from all chunk texts.
        context = " ".join(c.get("text", "") for c in authorized_timed_chunks)
        prompt = (
            "Summarize the following lecture content in up to 300 words. "
            "Focus on the main topics, important facts, and any conclusions."
        )
        answer_gen = OpenAIAnswerGenerator()
        summary = answer_gen.generate(prompt, [{"text": context, "chunk_id": "summary"}])
        # Return a single NoteEntry matching the contracts.
        from app.contracts import NoteEntry

        return [
            NoteEntry(
                note_id="generated-note",
                lecture_id=str(config.get("lecture_id", "")),
                version=str(config.get("processing_version", "0")),
                section="Summary",
                title="Lecture Summary",
                description=summary,
                supporting_segment_ids=[
                    c.get("chunk_id") for c in authorized_timed_chunks if c.get("chunk_id")
                ],
            )
        ]

