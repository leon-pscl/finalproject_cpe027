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

router = APIRouter(tags=["qa"])


class RetrieveRequest(BaseModel):
    question: str
    top_k: int = 5  # number of chunks to return (max 20)



class AnswerRequest(BaseModel):
    question: str
    top_k: int = Query(5, ge=1, le=20, description="Number of chunks to use for answer")


def _load_chunks(storage: StorageAdapter, owner_id: str, lecture_id: str) -> List[dict]:
    path = f"users/{owner_id}/{lecture_id}/chunks.json"
    try:
        data_bytes, _ = storage.read_object(path)
        return json.loads(data_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail={"error_code": ErrorCode.NOT_FOUND.value, "message": "Chunks not indexed"},
        ) from exc


def _embed_query(question: str, lecture_id: str, version: str) -> List[float]:
    adapters = adapter_bundle()
    embedder = adapters["embedder"]
    config = {"lecture_id": lecture_id, "version": version}
    vectors = embedder.embed([question], config)
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

    # Load stored chunks.
    stored_chunks = _load_chunks(storage, user.uid, lecture_id)
    if not stored_chunks:
        raise HTTPException(
            status_code=404,
            detail={"error_code": ErrorCode.NOT_FOUND.value, "message": "No chunks indexed"},
        )

    # Compute query embedding.
    query_vec = _embed_query(request.question, lecture_id, "v1")

    # Score chunks.
    scored = []
    for ch in stored_chunks:
        emb = ch.get("embedding") or []
        sim = _cosine_sim(query_vec, emb)
        scored.append((ch, sim))
    scored.sort(key=lambda x: x[1], reverse=True)
    top_chunks = [c for c, _ in scored[: request.top_k]]
    # Convert dicts to Chunk models for response.
    return [Chunk(**c) for c in top_chunks]


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

    # Load chunks and retrieve top results.
    stored_chunks = _load_chunks(storage, user.uid, lecture_id)
    if not stored_chunks:
        raise HTTPException(
            status_code=404,
            detail={"error_code": ErrorCode.NOT_FOUND.value, "message": "No chunks indexed"},
        )

    query_vec = _embed_query(request.question, lecture_id, "v1")
    scored = []
    for ch in stored_chunks:
        emb = ch.get("embedding") or []
        sim = _cosine_sim(query_vec, emb)
        scored.append((ch, sim))
    scored.sort(key=lambda x: x[1], reverse=True)
    top = [c for c, _ in scored[: request.top_k]]

    # Simple answer: concatenate chunk texts.
    answer_text = " ".join(c.get("text", "") for c in top)
    block = AnswerBlock(
        block_id=f"b-{uuid.uuid4().hex[:8]}",
        text=answer_text,
        source_ids=[c.get("chunk_id") for c in top],
    )
    sources = [
        SourceReference(
            source_id=c.get("chunk_id"),
            segment_id=None,
            start_s=c.get("start_s"),
            end_s=c.get("end_s"),
            text=c.get("text"),
        )
        for c in top
    ]
    answer = AnswerResponse(
        answer_id=f"ans-{uuid.uuid4().hex[:8]}",
        lecture_id=lecture_id,
        version="v1",
        processing_mode="real",
        status=AnswerStatus.ANSWERED,
        blocks=[block],
        sources=sources,
    )
    return answer
