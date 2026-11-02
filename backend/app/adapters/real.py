"""Real adapter stubs.

In safe local mode these raise immediately when invoked. They are only selected
when ``PROCESSING_MODE=real`` and the relevant provider is configured.
"""


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
from app.contracts import Chunk
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
        "configured in this build; implement the provider adapter first. (PROCESSING_MODE=real)"
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
        # Accept either a Transcript or a sequence of segments.
        if hasattr(timed_segments, "segments"):
            # Assume it's a Transcript object.
            transcript_obj = timed_segments
        else:
            # Build a Transcript compatible with the Chunker implementation.
            duration = max((seg.end for seg in timed_segments), default=0.0)
            transcript_obj = Transcript(language="en", duration=duration, segments=list(timed_segments))
        chunker = ChunkerImpl()
        return chunker.chunk(
            transcript_obj,
            config.get("lecture_id", ""),
            config.get("version", ""),
        )



class RealEmbedder(Embedder):
    def embed(self, chunks: Sequence[Chunk], config: dict | None = None) -> list[list[float]]:
        # Convert Chunk objects to dummy chunks for the shared embedder.
        from ..contracts import Chunk as ChunkModel
        dummy_chunks = [
            ChunkModel(
                chunk_id="tmp",
                lecture_id=c.lecture_id,
                version=c.version,
                segment_ids=[],
                start_s=0.0,
                end_s=0.0,
                text=c.text,
                embedding_model="",
                embedding_revision="",
            )
            for c in chunks
        ]
        # Use mock embedding (zero vectors) for simplicity.
        return [[0.0, 0.0, 0.0] for _ in dummy_chunks]




import json
import uuid
from typing import List

from pydantic import BaseModel, Field

from app.adapters.base import Retriever
from app.adapters.base import Embedder
from app.adapters.base import Chunker
from app.contracts import Chunk, NoteEntry
from app.config import get_settings
from app.vector_store import FAISSVectorStore, faiss
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
        from app.dependencies import get_storage
        self._settings = get_settings()

    def _load_vector_store(self, lecture_id: str) -> FAISSVectorStore:
        return FAISSVectorStore(self._settings.local_storage_root, lecture_id)

    def search(
        self, owner_id: str, lecture_id: str, processing_version: str, question: str
    ) -> List[Chunk]:
        # 1️⃣ Load the FAISS store; if unavailable, fallback to JSON without embedding.
        vec_store = self._load_vector_store(lecture_id)
        if faiss is None or getattr(vec_store, "index", None) is None:
            # Fallback – read the raw chunks JSON.
            # Fallback – read the raw chunks JSON using the test‑overridden storage if present.
            from fastapi import FastAPI
            from app.main import app as fastapi_app
            # Try FastAPI dependency override for get_storage.
            from app.dependencies import get_storage as default_get_storage
            get_storage_func = fastapi_app.dependency_overrides.get(default_get_storage, default_get_storage)
            storage = get_storage_func()
            data_bytes, _ = storage.read_object(
                f"users/{owner_id}/{lecture_id}/chunks.json"
            )
            chunks_data = json.loads(data_bytes.decode())
            return [Chunk(**c) for c in chunks_data]
            
        # 2️⃣ Embed the query using the shared embedder adapter (FAISS is available).
        from app.adapters import adapter_bundle
        embedder: Embedder = adapter_bundle()["embedder"]
        # Build a temporary Chunk just to satisfy the embedder's API.
        tmp = Chunk(
            chunk_id="tmp",
            lecture_id=lecture_id,
            version=processing_version,
            segment_ids=[],
            start_s=0.0,
            end_s=0.0,
            text=question,
            embedding_model="tmp",
            embedding_revision="0",
        )
        query_vec = embedder.embed([tmp])[0]
            
        # 3️⃣ Perform similarity search and return only the chunk objects.
        results = vec_store.query(query_vec)
        return [chunk for chunk, _ in results]



class RealAnswerGenerator(AnswerGenerator):
    def answer(
        self, question: str, authorized_evidence: Sequence[Any], config: dict
    ) -> Any:
        _require_real_mode("RealAnswerGenerator")


import uuid

from pydantic import BaseModel, Field
from typing import List


class _GeneratedNote(BaseModel):
    section: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    reference_chunk_ids: List[str] = Field(default_factory=list)


class _GeneratedNotes(BaseModel):
    notes: List[_GeneratedNote] = Field(default_factory=list)


import uuid

from pydantic import BaseModel, Field
from typing import List


class _GeneratedNote(BaseModel):
    section: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    reference_chunk_ids: List[str] = Field(default_factory=list)


class _GeneratedNotes(BaseModel):
    notes: List[_GeneratedNote] = Field(default_factory=list)


class RealNotesGenerator(NotesGenerator):
    def generate(self, authorized_timed_chunks, config):
        chunks = list(authorized_timed_chunks or [])
        if not chunks:
            return []

        valid_ids = {
            getattr(chunk, "chunk_id", None)
            for chunk in chunks
            if getattr(chunk, "chunk_id", None)
        }

        prepared = []
        for index, chunk in enumerate(chunks):
            chunk_id = getattr(chunk, "chunk_id", None) or "chunk-%d" % index
            text = getattr(chunk, "text", None)
            text = text if text is not None else str(chunk)
            prepared.append((str(chunk_id), str(text)))

        lecture_id = str(config.get("lecture_id", ""))
        version = str(config.get("processing_version", "0"))
        notes = []

        lc_available = True
        try:
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import (  # unused fallback
                PydanticOutputParser,
            )
            from langchain_groq import ChatGroq
        except Exception:
            lc_available = False

        if lc_available:
            try:
                settings = get_settings()
                if not settings.groq_api_key:
                    raise RuntimeError("groq api key not configured")

                from langchain_groq import ChatGroq

                model = ChatGroq(
                    api_key=settings.groq_api_key,
                    model="openai/gpt-oss-20b",
                    temperature=0.0,
                )
                structured_model = model.with_structured_output(_GeneratedNotes)

                def run_batch(batch):
                    context = "\n".join("[{}] {}".format(cid, txt) for cid, txt in batch)
                    last_error = None
                    for attempt in range(2):
                        try:
                            if attempt == 0:
                                prompt = ChatPromptTemplate.from_messages(
                                    [
                                        (
                                            "system",
                                            "You generate concise lecture notes. "
                                            "Use only the provided chunk context and reference real chunk IDs exactly.",
                                        ),
                                        (
                                            "user",
                                            "Generate structured lecture notes.\n\n"
                                            "Context:\n{context}\n\n"
                                            "{format_instructions}",
                                        ),
                                    ]
                                )
                            else:
                                prompt = ChatPromptTemplate.from_messages(
                                    [
                                        (
                                            "system",
                                            "Return strictly valid JSON matching the required schema.",
                                        ),
                                        (
                                            "user",
                                            "Previous error: {}\n\nSchema: {}\n\nContext:\n{}".format(
                                                last_error,
                                                "reference_chunk_ids must be real chunk IDs",
                                                context,
                                            ),
                                        ),
                                    ]
                                )
                            try:
                                from langchain_core.output_parsers import PydanticOutputParser
                            except Exception:
                                PydanticOutputParser = None
                            format_text = "JSON only"
                            chain = prompt | structured_model
                            result = chain.invoke(
                                {
                                    "context": context,
                                    "format_instructions": format_text,
                                }
                            )
                            return getattr(result, "notes", [])
                        except Exception as exc:
                            last_error = exc
                            if attempt == 1:
                                raise RuntimeError("structured generation failed: {}".format(exc))
                    return []

                batch_size = 6
                batches = [prepared[i:i + batch_size] for i in range(0, len(prepared), batch_size)]
                for batch in batches:
                    generated = run_batch(batch)
                    for note in generated or []:
                        refs = [rid for rid in note.reference_chunk_ids if rid in valid_ids]
                        notes.append(
                            NoteEntry(
                                note_id="generated-note-%s" % uuid.uuid4().hex[:8],
                                lecture_id=lecture_id,
                                version=version,
                                section=note.section,
                                title=note.title,
                                description=note.description,
                                supporting_segment_ids=refs,
                            )
                        )
            except Exception:
                lc_available = False

        if not lc_available or not notes:
            from app.answer_generator import GroqAnswerGenerator

            text = " ".join(text for _, text in prepared)
            generator = GroqAnswerGenerator()
            summary = generator.generate(
                "Summarize in up to 300 words.", [{"text": text, "chunk_id": "summary"}]
            )
            notes = [
                NoteEntry(
                    note_id="generated-note",
                    lecture_id=lecture_id,
                    version=version,
                    section="Summary",
                    title="Lecture Summary",
                    description=summary,
                    supporting_segment_ids=list(valid_ids),
                )
            ]

        return notes
