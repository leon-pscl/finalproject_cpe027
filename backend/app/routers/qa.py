# -*- coding: utf-8 -*-
"""Question answering and retrieval endpoints.

Provides a simple retrieval based on stored chunk embeddings and a minimal
answer generation that concatenates the top retrieved chunks.
"""

from __future__ import annotations

from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

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
from app.answer_generator import GroqAnswerGenerator

router = APIRouter(tags=["qa"])
import uuid

class RetrieveRequest(BaseModel):
    question: str
    top_k: int = 5  # number of chunks to return (max 20)

class AnswerRequest(BaseModel):
    question: str
    top_k: int = Query(5, ge=1, le=20, description="Number of chunks to use for answer")

def _embed_query(question: str, lecture_id: str, version: str) -> List[float]:
    """Embed a query using the shared embedder adapter."""
    adapters = adapter_bundle()
    embedder = adapters["embedder"]
    tmp = Chunk(
        chunk_id="tmp",
        lecture_id=lecture_id,
        version=version,
        segment_ids=[],
        start_s=0.0,
        end_s=0.0,
        text=question,
        embedding_model="tmp",
        embedding_revision="0",
    )
    vectors = embedder.embed([tmp])
    return vectors[0]

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
    # Use the shared retriever adapter (LangChain‑based).
    retriever = adapter_bundle()["retriever"]
    all_chunks = retriever.search(user.uid, lecture_id, "v1", request.question)
    return all_chunks[: request.top_k]

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
    # Retrieve top‑k chunks via the retriever.
    retriever = adapter_bundle()["retriever"]
    all_chunks = retriever.search(user.uid, lecture_id, "v1", request.question)
    top_chunks = all_chunks[: request.top_k]

    # Try to generate an answer via Groq.
    try:
        answer_gen = GroqAnswerGenerator()
        answer_text = answer_gen.generate(request.question, top_chunks)
        status = AnswerStatus.ANSWERED
    except Exception as exc:
        # Fallback: concatenate the retrieved passages.
        answer_text = " ".join(c.text for c in top_chunks)
        status = AnswerStatus.ANSWERED
        import logging
        logging.getLogger(__name__).warning(
            "LLM generation failed (%s); falling back to retrieved passages", exc
        )

    block = AnswerBlock(
        block_id=f"b-{uuid.uuid4().hex[:8]}",
        text=answer_text,
        source_ids=[c.chunk_id for c in top_chunks],
    )
    sources = [
        SourceReference(
            source_id=c.chunk_id,
            segment_id=None,
            start_s=c.start_s,
            end_s=c.end_s,
            text=c.text,
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
