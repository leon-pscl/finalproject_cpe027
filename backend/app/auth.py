"""Firebase ID token verification.

Owner identity is derived solely from the verified token uid. Client-provided
identifiers are never trusted.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status

from app.contracts import ErrorCode
from app.firebase import get_firebase_app


class AuthError(Exception):
    def __init__(self, code: ErrorCode, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class VerifiedUser:
    uid: str
    email: str | None = None
    claims: dict = None  # type: ignore[assignment]


def _http_exception(code: ErrorCode, detail: str) -> HTTPException:
    status_code = {
        ErrorCode.AUTH_REQUIRED: status.HTTP_401_UNAUTHORIZED,
        ErrorCode.SESSION_EXPIRED: status.HTTP_401_UNAUTHORIZED,
        ErrorCode.AUTH_INVALID: status.HTTP_401_UNAUTHORIZED,
    }.get(code, status.HTTP_401_UNAUTHORIZED)
    return HTTPException(
        status_code=status_code, detail={"error_code": code.value, "message": detail}
    )


def require_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError(ErrorCode.AUTH_REQUIRED, "Authorization header is required")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise AuthError(ErrorCode.AUTH_REQUIRED, "Bearer token is empty")
    return token


def verify_id_token(
    authorization: str | None = None,
    token: str | None = None,
    check_revoked: bool = True,
) -> VerifiedUser:
    """Verify a Firebase ID token and return the trusted uid."""
    raw_token = token or (
        require_bearer_token(authorization) if authorization else None
    )
    if not raw_token:
        raise AuthError(ErrorCode.AUTH_REQUIRED, "Firebase ID token is required")

    get_firebase_app()
    try:
        import firebase_admin  # noqa: F401
        from firebase_admin import auth as firebase_auth  # type: ignore
    except ImportError as exc:
        raise AuthError(
            ErrorCode.AUTH_INVALID,
            "firebase_admin is not installed; auth cannot be verified in safe local mode",
        ) from exc

    try:
        claims = firebase_auth.verify_id_token(raw_token, check_revoked=check_revoked)
    except (
        Exception
    ) as exc:  # firebase_admin raises specific subclasses; keep boundary broad
        message = str(exc).lower()
        if "expired" in message or "revoked" in message:
            raise AuthError(
                ErrorCode.SESSION_EXPIRED, "Session expired or revoked"
            ) from exc
        raise AuthError(ErrorCode.AUTH_INVALID, "Invalid authentication token") from exc

    uid = claims.get("uid") or claims.get("user_id") or claims.get("sub")
    if not uid:
        raise AuthError(ErrorCode.AUTH_INVALID, "Token missing uid claim")
    return VerifiedUser(uid=uid, email=claims.get("email"), claims=claims)
