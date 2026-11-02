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
from app.config import get_settings
from app.adapters import adapter_bundle


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

    # Try to generate an answer via LangChain Groq; fall back to retrieved passages.
    status = AnswerStatus.ANSWERED
    try:
        settings = get_settings()
        if not settings.groq_api_key:
            raise RuntimeError("groq api key not configured")
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_groq import ChatGroq

        model = ChatGroq(
            api_key=settings.groq_api_key,
            model="openai/gpt-oss-20b",
            temperature=0.0,
        )
        context_str = "\n\n".join(
            f"[Chunk {c.chunk_id} @ {float(c.start_s):.1f}s] {c.text}" for c in top_chunks
        )
        from app.web_search import search_web

        web_results = search_web(request.question, limit=5)
        web_str = "\n".join(
            f"- {result.get('title', '')}: {result.get('snippet', '')} ({result.get('url', '')})"
            for result in web_results
        ) or "No web results were available."
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are LectureFlow, a conversational study assistant for lecture transcripts. "
                    "Answer naturally and helpfully. If the question is unrelated to this lecture/session, explicitly say you cannot answer it because it is unrelated; do not use web results to fill that gap. "
                    "Otherwise, first use the lecture context; if the answer is missing there, "
                    "try the web search results before answering. If neither source contains the answer, say you do not know "
                    "and propose a useful next step. Verify relevant facts from the lecture context against the web search results; "
                    "if they conflict, explicitly state the conflict. "
                    "Keep answers concise and conversational, and cite relevant chunk IDs, audio timestamps like [0.0s], or URLs only for facts actually used. Cite an audio timestamp only when that transcript chunk directly supports the fact. Never invent sources.",
                ),
                ("user", "Question: {question}\n\nLecture context:\n{context}\n\nWeb search results:\n{web_results}"),
            ]
        )
        answer_text = (prompt | model).invoke(
            {"question": request.question, "context": context_str, "web_results": web_str}
        ).content.strip()
        answer_text = (prompt | model).invoke(
            {"question": request.question, "context": context_str}
        ).content.strip()
    except Exception as exc:
        answer_text = " ".join(c.text for c in top_chunks)
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