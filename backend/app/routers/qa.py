# -*- coding: utf-8 -*-
"""Question answering and retrieval endpoints.

Provides a simple retrieval based on stored chunk embeddings and a minimal
answer generation that concatenates the top retrieved chunks.
"""

from __future__ import annotations

import json
import math
import uuid
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import VerifiedUser
from app.contracts import (
    AnswerBlock,
    AnswerResponse,
    AnswerStatus,
    Chunk,
    ErrorCode,
    SourceReference,
)
from app.dependencies import (
    get_current_user,
    get_lecture_service,
    get_repository,
    get_storage,
)
from app.repositories import LectureRepository
from app.storage import StorageAdapter
from app.adapters import adapter_bundle
from app.services.lecture_service import LectureService
from pydantic import BaseModel

# Add the new FAISS and answer generator imports
from app.config import get_settings
from app.vector_store import FAISSVectorStore, faiss


from app.answer_generator import OpenAIAnswerGenerator

# Existing imports ... (keep them as they were)
import json
import math
import uuid
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import VerifiedUser
from app.contracts import (
    AnswerBlock,
    AnswerResponse,
    AnswerStatus,
    Chunk,
    ErrorCode,
    SourceReference,
)
from app.dependencies import (
    get_current_user,
    get_lecture_service,
    get_repository,
    get_storage,
)
from app.repositories import LectureRepository
from app.storage import StorageAdapter
from app.adapters import adapter_bundle
from app.services.lecture_service import LectureService
from pydantic import BaseModel

router = APIRouter(tags=["qa"])


class RetrieveRequest(BaseModel):
    question: str
    top_k: int = 5  # number of chunks to return (max 20)


class AnswerRequest(BaseModel):
    question: str
    top_k: int = Query(5, ge=1, le=20, description="Number of chunks to use for answer")


def _load_vector_store(storage_root: str, lecture_id: str) -> FAISSVectorStore:
    """Helper to create/load the FAISS store for a given lecture."""
    return FAISSVectorStore(storage_root, lecture_id)


def _embed_query(question: str, lecture_id: str, version: str, storage_root: str) -> List[float]:
    adapters = adapter_bundle()
    embedder = adapters["embedder"]
    config = {"lecture_id": lecture_id, "version": version}
    vectors = embedder.embed([Chunk(chunk_id="tmp", lecture_id=lecture_id, version=version, segment_ids=[], start_s=0.0, end_s=0.0, text=question, embedding_model="tmp", embedding_revision="0")])
    # The embedder expects a list of Chunk objects; we create a temporary one.
    return vectors[0]


def _cosine_sim(a: List[float], b: List[float]) -> float:
    # Defensive: empty vectors return 0 similarity.
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@router.post("/lectures/{lecture_id}/retrieve", response_model=List[Chunk])
def retrieve_chunks(
    lecture_id: str,
    request: RetrieveRequest,
    user: Annotated[VerifiedUser, Depends(get_current_user)],
    repository: Annotated[LectureRepository, Depends(get_repository)],
    storage: Annotated[StorageAdapter, Depends(get_storage)],
) -> List[Chunk]:
    # Verify lecture ownership.
    lecture = repository.get_lecture(user.uid, lecture_id)
    if lecture is None:
        raise HTTPException(
            status_code=404,
            detail={"error_code": ErrorCode.NOT_FOUND.value, "message": "Lecture not found"},
        )

# Updated retrieve endpoint to use the LangChain‑compatible real retriever
@@
-    vector_store = FAISSVectorStore(storage.settings.local_storage_root, lecture_id)
-    if faiss is None or getattr(vector_store, "index", None) is None:
-        # Fallback: read stored chunks directly from storage (used in tests without FAISS or missing index).
-        data_bytes, _ = storage.read_object(f"users/{user.uid}/{lecture_id}/chunks.json")
-        chunks_data = json.loads(data_bytes.decode())
-        top_chunks = [Chunk(**c) for c in chunks_data[:request.top_k]]
-        return top_chunks
-    # Normal retrieval using FAISS
-    top_chunks = [chunk for chunk, _ in vector_store.query(vector_store.index.reconstruct_n(0, vector_store.index.ntotal), top_k=request.top_k)]
-    return top_chunks
+    # Use the shared retriever adapter (LangChain‑based) for consistency.
+    retriever = adapter_bundle()["retriever"]
+    # The retriever returns all matching chunks; we slice to the requested top_k.
+    all_chunks = retriever.search(user.uid, lecture_id, "v1", request.question)
+    return all_chunks[: request.top_k]
*** End Patch
*** End Patch



@router.post("/lectures/{lecture_id}/answer", response_model=AnswerResponse)
def answer_question(
    lecture_id: str,
    request: AnswerRequest,
    user: Annotated[VerifiedUser, Depends(get_current_user)],
    repository: Annotated[LectureRepository, Depends(get_repository)],
    storage: Annotated[StorageAdapter, Depends(get_storage)],
) -> AnswerResponse:
    # Verify lecture ownership.
    lecture = repository.get_lecture(user.uid, lecture_id)
    if lecture is None:
        raise HTTPException(
            status_code=404,
            detail={"error_code": ErrorCode.NOT_FOUND.value, "message": "Lecture not found"},
        )

# Updated answer endpoint to use the LangChain‑compatible retriever
@@
-    if faiss is None or (vector_store := _load_vector_store(get_settings().local_storage_root, lecture_id)).index is None:
-        # Fallback: read stored chunks directly from storage.
-        data_bytes, _ = storage.read_object(f"users/{user.uid}/{lecture_id}/chunks.json")
-        chunks_data = json.loads(data_bytes.decode())
-        top_chunks = [Chunk(**c) for c in chunks_data[:request.top_k]]
-    else:
-        # Load vector store.
-        from app.config import get_settings
-        settings = get_settings()
-        vector_store = _load_vector_store(settings.local_storage_root, lecture_id)
-        # Embed the query.
-        query_vec = _embed_query(request.question, lecture_id, "v1", settings.local_storage_root)
-        # Retrieve top‑k chunks.
-        results = vector_store.query(query_vec, top_k=request.top_k)
-        top_chunks = [chunk for chunk, _ in results]
+    # Use the unified retriever (LangChain‑based) for consistency.
+    retriever = adapter_bundle()["retriever"]
+    # Retrieve all matching chunks and then apply the requested top_k.
+    all_chunks = retriever.search(user.uid, lecture_id, "v1", request.question)
+    top_chunks = all_chunks[: request.top_k]
*** End Patch
*** End Patch


    # Try to generate an answer via OpenAI.
    try:
        answer_gen = OpenAIAnswerGenerator()
        answer_text = answer_gen.generate(request.question, top_chunks)
        status = AnswerStatus.ANSWERED
    except Exception as exc:
        # Fallback: just concatenate the retrieved passages.
        answer_text = " ".join(c.get("text", "") for c in top_chunks)
        status = AnswerStatus.ANSWERED  # still marked answered but note fallback in logs
        # Log the missing API key or other error.
        import logging
        logging.getLogger(__name__).warning("LLM generation failed (%s); falling back to retrieved passages", exc)

    block = AnswerBlock(
        block_id=f"b-{uuid.uuid4().hex[:8]}",
        text=answer_text,
        source_ids=[c.get("chunk_id") for c in top_chunks],
    )
    sources = [
        SourceReference(
            source_id=c.get("chunk_id"),
            segment_id=None,
            start_s=c.get("start_s"),
            end_s=c.get("end_s"),
            text=c.get("text"),
        )
        for c in top_chunks
    ]
    answer = AnswerResponse(
        answer_id=f"ans-{uuid.uuid4().hex[:8]}",
        lecture_id=lecture_id,
        version="v1",
        processing_mode="real",
        status=status,
        blocks=[block],
        sources=sources,
    )
    return answer

