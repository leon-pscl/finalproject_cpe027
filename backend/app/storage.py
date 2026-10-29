"""Media storage adapters.

Local storage is used for safe local tests. Production uses Cloud Storage for
Firebase and signed URLs. Every object is verified server-side before a job
is enqueued.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app.config import Settings


class StoredObject:
    def __init__(
        self, storage_path: str, size_bytes: int, content_type: str | None = None
    ) -> None:
        self.storage_path = storage_path
        self.size_bytes = size_bytes
        self.content_type = content_type


class StorageAdapter(ABC):
    @abstractmethod
    def create_signed_upload_url(
        self, storage_path: str, content_type: str, expires_in_minutes: int = 15
    ) -> tuple[str, datetime]:
        raise NotImplementedError

    @abstractmethod
    def create_signed_download_url(
        self, storage_path: str, expires_in_minutes: int = 15
    ) -> tuple[str, datetime]:
        raise NotImplementedError

    @abstractmethod
    def verify_signature(
        self, storage_path: str, expires_epoch: int, signature: str
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def verify_object(
        self,
        storage_path: str,
        expected_size: int | None = None,
        expected_content_type: str | None = None,
    ) -> StoredObject:
        raise NotImplementedError

    @abstractmethod
    def save_object(
        self, storage_path: str, data: bytes, content_type: str | None = None
    ) -> StoredObject:
        raise NotImplementedError

    @abstractmethod
    def read_object(self, storage_path: str) -> tuple[bytes, str | None]:
        """Return object bytes and content type for a signed media read."""
        raise NotImplementedError

    @abstractmethod
    def delete_object(self, storage_path: str) -> None:
        raise NotImplementedError


class LocalStorageAdapter(StorageAdapter):
    """Filesystem adapter with HMAC-signed upload URLs."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = Path(settings.local_storage_root)
        self.secret = settings.storage_signed_url_secret.encode("utf-8")
        self.root.mkdir(parents=True, exist_ok=True)

    def _full_path(self, storage_path: str) -> Path:
        target = (self.root / storage_path).resolve()
        root = self.root.resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError("storage path escapes the local storage root") from exc
        return target

    def _metadata_path(self, storage_path: str) -> Path:
        full = self._full_path(storage_path)
        return full.with_suffix(full.suffix + ".metadata.json")

    def _sign(self, storage_path: str, expires_epoch: int) -> str:
        message = f"{storage_path}:{expires_epoch}".encode()
        return hmac.new(self.secret, message, hashlib.sha256).hexdigest()

    def create_signed_upload_url(
        self, storage_path: str, content_type: str, expires_in_minutes: int = 15
    ) -> tuple[str, datetime]:
        expires_at = datetime.now(UTC) + timedelta(minutes=expires_in_minutes)
        expires_epoch = int(expires_at.timestamp())
        signature = self._sign(storage_path, expires_epoch)
        url = (
            f"/api/storage/upload/{quote(storage_path, safe='/')}"
            f"?expires={expires_epoch}&signature={signature}"
        )
        # Store declared content type so local tests can write through the URL.
        self._write_metadata(storage_path, content_type)
        return url, expires_at

    def create_signed_download_url(
        self, storage_path: str, expires_in_minutes: int = 15
    ) -> tuple[str, datetime]:
        expires_at = datetime.now(UTC) + timedelta(minutes=expires_in_minutes)
        expires_epoch = int(expires_at.timestamp())
        signature = self._sign(storage_path, expires_epoch)
        url = (
            f"/api/storage/download/{quote(storage_path, safe='/')}"
            f"?expires={expires_epoch}&signature={signature}"
        )
        return url, expires_at

    def verify_signature(
        self, storage_path: str, expires_epoch: int, signature: str
    ) -> bool:
        try:
            self._full_path(storage_path)
        except ValueError:
            return False
        if expires_epoch < int(datetime.now(UTC).timestamp()):
            return False
        expected = self._sign(storage_path, expires_epoch)
        return hmac.compare_digest(expected, signature)

    def verify_object(
        self,
        storage_path: str,
        expected_size: int | None = None,
        expected_content_type: str | None = None,
    ) -> StoredObject:
        path = self._full_path(storage_path)
        if not path.is_file():
            raise ValueError("stored object does not exist")
        size = path.stat().st_size
        if size <= 0:
            raise ValueError("stored object is empty")
        if expected_size is not None and size != expected_size:
            raise ValueError("stored object size does not match")
        content_type = self._read_metadata(storage_path)
        if expected_content_type is not None and (
            content_type is None or content_type != expected_content_type
        ):
            raise ValueError("stored object content type does not match")
        if content_type is None:
            content_type = mimetypes.guess_type(path.name)[0]
        return StoredObject(storage_path, size, content_type)

    def save_object(
        self, storage_path: str, data: bytes, content_type: str | None = None
    ) -> StoredObject:
        path = self._full_path(storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        if content_type:
            self._write_metadata(storage_path, content_type)
        return StoredObject(storage_path, len(data), content_type)

    def read_object(self, storage_path: str) -> tuple[bytes, str | None]:
        path = self._full_path(storage_path)
        if not path.is_file():
            raise FileNotFoundError("stored object does not exist")
        if path.stat().st_size <= 0:
            raise ValueError("stored object is empty")
        content_type = self._read_metadata(storage_path)
        if content_type is None:
            content_type = mimetypes.guess_type(path.name)[0]
        return path.read_bytes(), content_type

    def download_object(self, storage_path: str) -> tuple[bytes, str | None]:
        return self.read_object(storage_path)

    def get_object(self, storage_path: str) -> tuple[bytes, str | None]:
        return self.read_object(storage_path)

    def open_object(self, storage_path: str) -> tuple[bytes, str | None]:
        return self.read_object(storage_path)

    def delete_object(self, storage_path: str) -> None:
        path = self._full_path(storage_path)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            self._metadata_path(storage_path).unlink(missing_ok=True)
        except OSError:
            pass

    def _write_metadata(self, storage_path: str, content_type: str) -> None:
        path = self._metadata_path(storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"content_type": content_type}), encoding="utf-8")

    def _read_metadata(self, storage_path: str) -> str | None:
        path = self._metadata_path(storage_path)
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("content_type")
        except (OSError, json.JSONDecodeError):
            return None


class FirebaseStorageAdapter(StorageAdapter):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _blob(self, storage_path: str) -> Any:
        from app.firebase import get_storage_bucket

        return get_storage_bucket().blob(storage_path)

    def create_signed_upload_url(
        self, storage_path: str, content_type: str, expires_in_minutes: int = 15
    ) -> tuple[str, datetime]:
        expires_at = datetime.now(UTC) + timedelta(minutes=expires_in_minutes)
        url = self._blob(storage_path).generate_signed_url(
            version="v4",
            expiration=expires_at - datetime.now(UTC),
            method="PUT",
            content_type=content_type,
        )
        return url, expires_at

    def create_signed_download_url(
        self, storage_path: str, expires_in_minutes: int = 15
    ) -> tuple[str, datetime]:
        expires_at = datetime.now(UTC) + timedelta(minutes=expires_in_minutes)
        url = self._blob(storage_path).generate_signed_url(
            version="v4",
            expiration=expires_at - datetime.now(UTC),
            method="GET",
        )
        return url, expires_at

    def verify_signature(
        self, storage_path: str, expires_epoch: int, signature: str
    ) -> bool:
        del storage_path, expires_epoch, signature
        return True

    def verify_object(
        self,
        storage_path: str,
        expected_size: int | None = None,
        expected_content_type: str | None = None,
    ) -> StoredObject:
        blob = self._blob(storage_path)
        blob.reload()
        if not getattr(blob, "exists", True):
            raise ValueError("stored object does not exist")
        size = int(blob.size or 0)
        if size <= 0:
            raise ValueError("stored object is empty")
        if expected_size is not None and size != expected_size:
            raise ValueError("stored object size does not match")
        content_type = getattr(blob, "content_type", None)
        if expected_content_type is not None and (
            content_type is None or content_type != expected_content_type
        ):
            raise ValueError("stored object content type does not match")
        return StoredObject(storage_path, size, content_type)

    def save_object(
        self, storage_path: str, data: bytes, content_type: str | None = None
    ) -> StoredObject:
        blob = self._blob(storage_path)
        blob.upload_from_string(data, content_type=content_type)
        return StoredObject(storage_path, len(data), content_type)

    def read_object(self, storage_path: str) -> tuple[bytes, str | None]:
        blob = self._blob(storage_path)
        blob.reload()
        if not getattr(blob, "exists", True):
            raise FileNotFoundError("stored object does not exist")
        size = int(blob.size or 0)
        if size <= 0:
            raise ValueError("stored object is empty")
        return blob.download_as_bytes(), getattr(blob, "content_type", None)

    def download_object(self, storage_path: str) -> tuple[bytes, str | None]:
        return self.read_object(storage_path)

    def get_object(self, storage_path: str) -> tuple[bytes, str | None]:
        return self.read_object(storage_path)

    def open_object(self, storage_path: str) -> tuple[bytes, str | None]:
        return self.read_object(storage_path)

    def delete_object(self, storage_path: str) -> None:
        from contextlib import suppress

        with suppress(Exception):
            self._blob(storage_path).delete()
