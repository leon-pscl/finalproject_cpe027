"""Endpoint to retrieve a signed URL for the DSP‑enhanced audio asset.

The DSP audio is stored by the worker at ``users/{owner_id}/{lecture_id}/dsp.wav``.
Clients can request a signed download URL which they can use in an <audio> tag.
"""

from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_storage
from app.storage import StorageAdapter

router = APIRouter(tags=["dsp"])

@router.get("/dsp/{owner_id}/{lecture_id}/url")
def get_dsp_signed_url(
    owner_id: str,
    lecture_id: str,
    storage: StorageAdapter = Depends(get_storage),
):
    storage_path = f"users/{owner_id}/{lecture_id}/dsp.wav"
    try:
        signed_url, _ = storage.create_signed_download_url(storage_path, expires_in_minutes=15)
    except Exception:
        raise HTTPException(status_code=404, detail="DSP audio not found")
    return {"url": signed_url}
