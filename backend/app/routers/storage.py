"""Local temporary storage endpoints for signed uploads."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.contracts import ErrorCode
from app.dependencies import get_storage
from app.storage import StorageAdapter

router = APIRouter(tags=["storage"])


@router.put("/storage/upload/{storage_path:path}")
async def signed_upload(
    storage_path: str,
    request: Request,
    expires: int,
    signature: str,
    storage: Annotated[StorageAdapter, Depends(get_storage)],
):
    if not storage.verify_signature(storage_path, expires, signature):
        return JSONResponse(
            status_code=400,
            content={
                "detail": {
                    "error_code": ErrorCode.INVALID_REQUEST.value,
                    "message": "Invalid or expired upload signature",
                }
            },
        )
    data = await request.body()
    content_type = request.headers.get("content-type", "").split(";")[0].strip() or None
    try:
        stored = storage.save_object(storage_path, data, content_type)
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": ErrorCode.STORED_OBJECT_MISMATCH.value,
                "message": str(exc),
            },
        ) from exc
    return {"status": "stored", "size_bytes": stored.size_bytes}
