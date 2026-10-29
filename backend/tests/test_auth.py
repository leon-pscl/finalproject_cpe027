from app.auth import require_bearer_token
from app.contracts import ErrorCode


def test_require_bearer_token_rejects_missing_header() -> None:
    try:
        require_bearer_token(None)
    except Exception as exc:  # noqa: BLE001 - broad to assert custom error code
        assert getattr(exc, "code", None) == ErrorCode.AUTH_REQUIRED
    else:
        raise AssertionError("expected AuthError")


def test_require_bearer_token_extracts_token() -> None:
    assert require_bearer_token("Bearer token-value") == "token-value"
