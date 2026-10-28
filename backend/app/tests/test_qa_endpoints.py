import json
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_current_user, get_storage, get_repository
from app.storage import StorageAdapter
from app.auth import VerifiedUser

from app.repositories import InMemoryLectureRepository

def _override_current_user() -> VerifiedUser:
    """Return a dummy verified user for tests."""
    return VerifiedUser(uid="test_user", email="test@example.com")

class _DummyStorage(StorageAdapter):
    """Minimal storage that returns preset chunks.json content."""

    def __init__(self, chunks: list[dict]):
        self._chunks = chunks

    # Methods not used in QA tests can raise NotImplementedError.
    def create_signed_upload_url(self, *_, **__):  # pragma: no cover
        raise NotImplementedError

    def create_signed_download_url(self, *_, **__):  # pragma: no cover
        raise NotImplementedError

    def verify_signature(self, *_, **__):  # pragma: no cover
        raise NotImplementedError

    def verify_object(self, *_, **__):  # pragma: no cover
        raise NotImplementedError

    def save_object(self, *_, **__):  # pragma: no cover
        raise NotImplementedError

    def read_object(self, storage_path: str):
        """Return the stored chunks JSON for the requested path."""
        if storage_path.endswith("chunks.json"):
            return json.dumps(self._chunks).encode("utf-8"), "application/json"
        raise FileNotFoundError(f"Unexpected path: {storage_path}")

    def delete_object(self, *_, **__):  # pragma: no cover
        raise NotImplementedError


def _override_storage() -> StorageAdapter:
    # Two simple chunks with deterministic embeddings.
    chunks = [
        {
            "chunk_id": "c1",
            "lecture_id": "lecture123",
            "version": "v1",
            "segment_ids": ["s1"],
            "start_s": 0.0,
            "end_s": 5.0,
            "text": "Hello world",
            "embedding": [1.0, 0.0, 0.0],
            "embedding_model": "mock",
            "embedding_revision": "0",
        },
        {
            "chunk_id": "c2",
            "lecture_id": "lecture123",
            "version": "v1",
            "segment_ids": ["s2"],
            "start_s": 5.0,
            "end_s": 10.0,
            "text": "Second chunk",
            "embedding": [0.0, 1.0, 0.0],
            "embedding_model": "mock",
            "embedding_revision": "0",
        },
    ]
    return _DummyStorage(chunks)

def _override_repository() -> InMemoryLectureRepository:
    repo = InMemoryLectureRepository()
    # Create a dummy lecture matching the test user and lecture ID.
    repo.create_lecture(
        owner_id="test_user",
        lecture_id="lecture123",
        title="Test Lecture",
        storage_path="dummy/path",
        declared_type="audio/wav",
        declared_size_bytes=123,
    )
    return repo
app.dependency_overrides[get_current_user] = _override_current_user
app.dependency_overrides[get_storage] = _override_storage
app.dependency_overrides[get_repository] = _override_repository
client = TestClient(app)


def test_retrieve_chunks():
    """Retrieve top‑k chunks for a lecture and verify the response shape."""
    resp = client.post(
        "/api/lectures/lecture123/retrieve",
        json={"question": "world", "top_k": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["chunk_id"] == "c1"


def test_answer_question():
    """Answer a question using the stored chunks and the mock embedder."""
    resp = client.post(
        "/api/lectures/lecture123/answer",
        json={"question": "world", "top_k": 2},
    )
    assert resp.status_code == 200
    ans = resp.json()
    # The mock answer generator should return a status of ANSWERED.
    assert ans["status"] == "answered"
    # The answer text should contain the concatenated chunk texts.
    assert "Hello world" in ans["blocks"][0]["text"]
    assert "Second chunk" in ans["blocks"][0]["text"]
