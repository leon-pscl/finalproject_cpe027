"""Local temporary storage endpoints for signed uploads and reads."""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response

from app.contracts import ErrorCode, SignedDownloadUrlResponse
from app.dependencies import get_storage
from app.storage import StorageAdapter

router = APIRouter(tags=["storage"])


@router.put("/storage/upload/{storage_path:path}")
async def signed_upload(
    storage_path: str,
    request: Request,
    expires: int,
    signature: str,
    storage: StorageAdapter = Depends(get_storage),
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


@router.get(
    "/storage/download-url/{storage_path:path}",
    response_model=SignedDownloadUrlResponse,
)
def signed_download_url(
    storage_path: str,
    storage: StorageAdapter = Depends(get_storage),
    expires_in_minutes: int = Query(default=15, ge=1, le=1440),
):
    try:
        signed_url, expires_at = storage.create_signed_download_url(
            storage_path, expires_in_minutes=expires_in_minutes
        )
    except (OSError, ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "message": str(exc),
            },
        ) from exc
    return SignedDownloadUrlResponse(
        storage_path=storage_path,
        signed_download_url=signed_url,
        signed_url=signed_url,
        download_url=signed_url,
        expires_at=expires_at,
    )


@router.get("/storage/download/{storage_path:path}")
def signed_read(
    storage_path: str,
    expires: int,
    signature: str,
    storage: StorageAdapter = Depends(get_storage),
):
    if not storage.verify_signature(storage_path, expires, signature):
        return JSONResponse(
            status_code=400,
            content={
                "detail": {
                    "error_code": ErrorCode.INVALID_REQUEST.value,
                    "message": "Invalid or expired download signature",
                }
            },
        )
    try:
        data, content_type = storage.read_object(storage_path)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "message": str(exc),
            },
        ) from exc
    except (OSError, ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": ErrorCode.STORED_OBJECT_MISMATCH.value,
                "message": str(exc),
            },
        ) from exc
    return Response(
        content=data,
        media_type=content_type or "application/octet-stream",
        headers={"cache-control": "private, max-age=300"},
    )
