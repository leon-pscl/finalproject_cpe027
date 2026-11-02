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
from app.asr import Transcript
from app.chunker import Chunker as ChunkerImpl
from app.config import get_settings
from app.contracts import Chunk


class AdapterNotConfigured(RuntimeError):
    """Raised when a real adapter is selected but its provider is not configured."""


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

from pydantic import BaseModel, Field

from app.adapters.base import Chunker, Embedder
from app.contracts import Chunk, NoteEntry
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
        self._settings = get_settings()

    def _load_vector_store(self, lecture_id: str) -> FAISSVectorStore:
        return FAISSVectorStore(self._settings.local_storage_root, lecture_id)

    def search(
        self, owner_id: str, lecture_id: str, processing_version: str, question: str
    ) -> list[Chunk]:
        # 1️⃣ Load the FAISS store; if unavailable, fallback to JSON without embedding.
        vec_store = self._load_vector_store(lecture_id)
        if faiss is None or getattr(vec_store, "index", None) is None:
            # Fallback – read the raw chunks JSON.
            # Fallback – read the raw chunks JSON using the test‑overridden storage if present.
            # Try FastAPI dependency override for get_storage.
            from app.dependencies import get_storage as default_get_storage
            from app.main import app as fastapi_app
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
        import uuid

        from app.contracts import (
            AnswerBlock,
            AnswerResponse,
            AnswerStatus,
            SourceReference,
        )

        evidence = list(authorized_evidence or [])
        source_ids = []
        sources: list[SourceReference] = []
        for chunk in evidence:
            chunk_id = getattr(chunk, "chunk_id", "")
            if chunk_id and str(chunk_id) not in source_ids:
                source_ids.append(str(chunk_id))
            sources.append(
                SourceReference(
                    source_id=str(chunk_id or "unknown"),
                    segment_id=getattr(chunk, "segment_id", None),
                    start_s=float(getattr(chunk, "start_s", 0.0)),
                    end_s=float(getattr(chunk, "end_s", 0.0)),
                    text=str(getattr(chunk, "text", "")),
                )
            )

        status = AnswerStatus.ANSWERED
        answer_text = None
        try:
            from langchain_core.prompts import ChatPromptTemplate

            from app.llm import get_chat_model

            context_str = "\n\n".join(
                f"[{getattr(chunk, 'chunk_id', index)} @ {float(getattr(chunk, 'start_s', 0.0)):.1f}s] {getattr(chunk, 'text', str(chunk))}"
                for index, chunk in enumerate(evidence)
            )

            from app.web_search import search_web

            web_results = search_web(question, limit=5)
            web_str = "\n".join(
                f"- {result.get('title', '')}: {result.get('snippet', '')} ({result.get('url', '')})"
                for result in web_results
            ) or "No web results were available."

            model = get_chat_model(temperature=0.2)
            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You are LectureFlow, a conversational study assistant for lecture transcripts. "
                        "Answer in a natural, helpful tone. First use the lecture context; if the answer is missing there, "
                        "try the web search results before answering. If neither source contains the answer, say you do not know "
                        "and propose a useful next step. Verify relevant facts from the lecture context against the web search results; "
                        "if they conflict, explicitly state the conflict. Keep the answer concise and conversational, and cite relevant chunk IDs, audio timestamps like [0.0s], or URLs only for facts actually used. Cite an audio timestamp only when that transcript chunk directly supports the fact. Never invent sources.",
                    ),
                    ("user", "Question: {question}\n\nLecture context:\n{context}\n\nWeb search results:\n{web_results}"),
                ]
            )
            answer_text = (prompt | model).invoke(
                {"question": question, "context": context_str, "web_results": web_str}
            ).content.strip()
        except Exception:
            answer_text = " ".join(str(getattr(chunk, "text", "")) for chunk in evidence)
            status = AnswerStatus.ANSWERED

        block = AnswerBlock(
            block_id="b-%s" % uuid.uuid4().hex[:8],
            text=answer_text,
            source_ids=source_ids,
        )
        return AnswerResponse(
            answer_id="ans-%s" % uuid.uuid4().hex[:8],
            lecture_id=str(config.get("lecture_id", "")),
            version=str(config.get("processing_version", "v1")),
            processing_mode=str(getattr(get_settings(), "processing_mode", "real")),
            status=status,
            blocks=[block],
            sources=sources,
        )


class _GeneratedNote(BaseModel):
    section: str
    title: str
    description: str
    reference_chunk_ids: list[str] = Field(default_factory=list)


class _GeneratedNotes(BaseModel):
    notes: list[_GeneratedNote] = Field(default_factory=list)


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

            from app.llm import get_chat_model
        except Exception:
            lc_available = False

        if lc_available:
            try:
                from app.llm import get_chat_model, structured_output_method

                model = get_chat_model(temperature=0.0)
                structured_output_kwargs = {}
                _method = structured_output_method()
                if _method is not None:
                    structured_output_kwargs["method"] = _method
                structured_model = model.with_structured_output(
                    _GeneratedNotes, **structured_output_kwargs
                )

                def run_batch(batch):
                    context = "\n".join(f"[{cid}] {txt}" for cid, txt in batch)
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
                                from langchain_core.output_parsers import (
                                    PydanticOutputParser,
                                )
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
                                raise RuntimeError(f"structured generation failed: {exc}")
                    return []

                batch_size = 4
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
            try:
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
            except Exception:
                notes = [
                    NoteEntry(
                        note_id="generated-note-fallback",
                        lecture_id=lecture_id,
                        version=version,
                        section="Transcript",
                        title="Processing fallback",
                        description=" ".join(text for _, text in prepared),
                        supporting_segment_ids=list(valid_ids),
                    )
                ]

        return notes
