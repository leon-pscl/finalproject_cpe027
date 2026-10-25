"""Firebase Admin SDK wiring (API + worker).

Safe local mode: if the SDK is not installed or the project is not configured,
functions raise a clear error instead of failing at import time.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from app.config import get_settings


class FirebaseNotConfigured(RuntimeError):
    pass


def _firebase_admin() -> Any:
    try:
        import firebase_admin  # type: ignore
        from firebase_admin import credentials  # type: ignore

        return firebase_admin, credentials
    except ImportError as exc:
        raise RuntimeError(
            "firebase_admin is not installed; add it to backend/requirements.txt "
            "and install dependencies (safe local mode)."
        ) from exc


@lru_cache(maxsize=1)
def get_firebase_app() -> Any:
    settings = get_settings()
    firebase_admin, credentials = _firebase_admin()

    # Allow Firebase emulators in local development.
    if settings.firestore_emulator_host:
        os.environ.setdefault(
            "FIRESTORE_EMULATOR_HOST", settings.firestore_emulator_host
        )
    if settings.firebase_storage_emulator_host:
        os.environ.setdefault(
            "FIREBASE_STORAGE_EMULATOR_HOST", settings.firebase_storage_emulator_host
        )
    if settings.firebase_auth_emulator_host:
        os.environ.setdefault(
            "FIREBASE_AUTH_EMULATOR_HOST", settings.firebase_auth_emulator_host
        )

    project_id = settings.firebase_project_id
    if not project_id and not settings.firestore_emulator_host:
        raise FirebaseNotConfigured(
            "FIREBASE_PROJECT_ID is required unless using emulators"
        )

    options: dict[str, Any] = {}
    if project_id:
        options["projectId"] = project_id
    if settings.firebase_storage_bucket:
        options["storageBucket"] = settings.firebase_storage_bucket

    app = firebase_admin.get_app() if _has_default_app() else None
    if app is not None:
        return app

    if settings.firebase_credentials_path:
        if not os.path.exists(settings.firebase_credentials_path):
            raise FirebaseNotConfigured(
                f"Firebase credentials file does not exist: {settings.firebase_credentials_path}"
            )
        cred = credentials.Certificate(settings.firebase_credentials_path)
        return firebase_admin.initialize_app(cred, options if options else None)

    # Application Default Credentials (appropriate on Cloud Run).
    return firebase_admin.initialize_app(
        credentials.ApplicationDefault() if project_id else None,
        options if options else None,
    )


def _has_default_app() -> bool:
    try:
        import firebase_admin

        firebase_admin.get_app()
        return True
    except (ValueError, RuntimeError):
        return False


def get_firestore_client() -> Any:
    get_firebase_app()
    from firebase_admin import firestore  # type: ignore

    return firestore.client()


def get_storage_bucket() -> Any:
    get_firebase_app()
    from firebase_admin import storage  # type: ignore

    settings = get_settings()
    if settings.firebase_storage_bucket:
        return storage.bucket(settings.firebase_storage_bucket)
    return storage.bucket()
