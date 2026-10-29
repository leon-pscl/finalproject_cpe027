# -*- coding: utf-8 -*-
"""Question answering and retrieval endpoints.

Provides retrieval based on FAISS vector store or stored chunk embeddings,
and answer generation via OpenAI LLM or concatenation fallback.
"""

from __future__ import annotations

import json
import logging
import math
import uuid
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.adapters import adapter_bundle
from app.answer_generator import OpenAIAnswerGenerator
from app.auth import VerifiedUser
from app.config import get_settings
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
    get_repository,
    get_storage,
)
from app.repositories import LectureRepository
from app.storage import StorageAdapter
from app.vector_store import FAISSVectorStore

logger = logging.getLogger(__name__)

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


def _load_chunks(storage: StorageAdapter, owner_id: str, lecture_id: str) -> List[dict]:
    path = f"users/{owner_id}/{lecture_id}/chunks.json"
    try:
        data_bytes, _ = storage.read_object(path)
        return json.loads(data_bytes)
    except Exception:
        return []


def _embed_query(question: str, lecture_id: str, version: str, storage_root: str) -> List[float]:
    adapters = adapter_bundle()
    embedder = adapters["embedder"]
    config = {"lecture_id": lecture_id, "version": version}
    chunk = Chunk(
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
    vectors = embedder.embed([chunk], config)
    return vectors[0]


def _cosine_sim(a: List[float], b: List[float]) -> float:
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
    lecture = repository.get_lecture(user.uid, lecture_id)
    if lecture is None:
        raise HTTPException(
            status_code=404,
            detail={"error_code": ErrorCode.NOT_FOUND.value, "message": "Lecture not found"},
        )

    settings = get_settings()
    query_vec = _embed_query(request.question, lecture_id, "v1", settings.local_storage_root)

    top_chunks: List[dict] = []
    try:
        vector_store = _load_vector_store(settings.local_storage_root, lecture_id)
        results = vector_store.query(query_vec, top_k=request.top_k)
        top_chunks = [chunk for chunk, _ in results]
    except Exception as exc:
        logger.debug("FAISS query failed (%s); checking storage chunks fallback", exc)

    if not top_chunks:
        stored_chunks = _load_chunks(storage, user.uid, lecture_id)
        if stored_chunks:
            scored = []
            for ch in stored_chunks:
                emb = ch.get("embedding") or []
                sim = _cosine_sim(query_vec, emb)
                scored.append((ch, sim))
            scored.sort(key=lambda x: x[1], reverse=True)
            top_chunks = [c for c, _ in scored[: request.top_k]]

    return [Chunk(**chunk) for chunk in top_chunks]


@router.post("/lectures/{lecture_id}/answer", response_model=AnswerResponse)
def answer_question(
    lecture_id: str,
    request: AnswerRequest,
    user: Annotated[VerifiedUser, Depends(get_current_user)],
    repository: Annotated[LectureRepository, Depends(get_repository)],
    storage: Annotated[StorageAdapter, Depends(get_storage)],
) -> AnswerResponse:
    lecture = repository.get_lecture(user.uid, lecture_id)
    if lecture is None:
        raise HTTPException(
            status_code=404,
            detail={"error_code": ErrorCode.NOT_FOUND.value, "message": "Lecture not found"},
        )

    settings = get_settings()
    query_vec = _embed_query(request.question, lecture_id, "v1", settings.local_storage_root)

    top_chunks: List[dict] = []
    try:
        vector_store = _load_vector_store(settings.local_storage_root, lecture_id)
        results = vector_store.query(query_vec, top_k=request.top_k)
        top_chunks = [chunk for chunk, _ in results]
    except Exception as exc:
        logger.debug("FAISS query failed (%s); checking storage chunks fallback", exc)

    if not top_chunks:
        stored_chunks = _load_chunks(storage, user.uid, lecture_id)
        if stored_chunks:
            scored = []
            for ch in stored_chunks:
                emb = ch.get("embedding") or []
                sim = _cosine_sim(query_vec, emb)
                scored.append((ch, sim))
            scored.sort(key=lambda x: x[1], reverse=True)
            top_chunks = [c for c, _ in scored[: request.top_k]]

    try:
        answer_gen = OpenAIAnswerGenerator()
        answer_text = answer_gen.generate(request.question, top_chunks)
        status = AnswerStatus.ANSWERED
    except Exception as exc:
        answer_text = " ".join(c.get("text", "") for c in top_chunks)
        status = AnswerStatus.ANSWERED
        logger.warning("LLM generation failed (%s); falling back to retrieved passages", exc)

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
    return AnswerResponse(
        answer_id=f"ans-{uuid.uuid4().hex[:8]}",
        lecture_id=lecture_id,
        version="v1",
        processing_mode="real",
        status=status,
        blocks=[block],
        sources=sources,
    )
