'''Stub Firebase module for local demo.

Provides minimal no-op implementations so the rest of the code can import
functions without requiring firebase-admin.
'''

from __future__ import annotations

from typing import Any

# Settings are retained for compatibility but not used.
from app.config import get_settings


class FirebaseNotConfigured(RuntimeError):
    pass


def get_firebase_app() -> Any:
    """Return a dummy object representing the Firebase app.

    In the demo environment we do not connect to Firebase, so this is a no-op.
    """
    return None


def get_firestore_client() -> Any:
    """Return a simple in‑memory mock Firestore client.

    The mock implements a minimal ``collection(name)`` API used by the app.
    """
    class MockDoc:
        def __init__(self):
            self._data = {}
        def get(self):
            return type("Doc", (), {"to_dict": lambda self: self._data})()
        def set(self, data):
            self._data.update(data)

    class MockCollection:
        def __init__(self):
            self._docs: dict[str, MockDoc] = {}
        def doc(self, doc_id: str) -> MockDoc:
            if doc_id not in self._docs:
                self._docs[doc_id] = MockDoc()
            return self._docs[doc_id]

    class MockClient:
        def __init__(self):
            self._collections: dict[str, MockCollection] = {}
        def collection(self, name: str) -> MockCollection:
            if name not in self._collections:
                self._collections[name] = MockCollection()
            return self._collections[name]

    return MockClient()


def get_storage_bucket() -> Any:
    """Return a dummy storage bucket object.

    The returned object provides a ``blob(name)`` method returning a mock with
    ``upload_from_string`` and ``download_as_string`` methods.
    """
    class MockBlob:
        def __init__(self):
            self._data = b""
        def upload_from_string(self, data: bytes):
            self._data = data
        def download_as_string(self) -> bytes:
            return self._data

    class MockBucket:
        def __init__(self):
            self._blobs: dict[str, MockBlob] = {}
        def blob(self, name: str) -> MockBlob:
            if name not in self._blobs:
                self._blobs[name] = MockBlob()
            return self._blobs[name]

    return MockBucket()
