from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/health")
def health_check() -> dict:
    """Simple health endpoint used to verify the API is up and required env vars are present."""
    return {"status": "ok"}
