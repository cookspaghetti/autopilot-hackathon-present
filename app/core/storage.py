# app/core/storage.py
"""
Storage abstraction layer for file operations.

Supports:
- Local filesystem (development)
- Google Cloud Storage (production)

Usage:
    from app.core.storage import storage

    # Upload a file
    url = await storage.upload("path/to/file.pdf", file_bytes, content_type="application/pdf")

    # Download a file
    data = await storage.download("path/to/file.pdf")

    # Delete a file
    await storage.delete("path/to/file.pdf")

    # List files
    files = await storage.list_files("path/to/folder/")
"""

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from functools import partial
from pathlib import Path
from typing import BinaryIO, List, Optional, Union

log = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def upload(
        self,
        path: str,
        data: Union[bytes, BinaryIO],
        content_type: Optional[str] = None,
    ) -> str:
        """Upload a file and return its URL."""
        pass

    @abstractmethod
    async def download(self, path: str) -> bytes:
        """Download a file and return its contents."""
        pass

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete a file. Returns True if successful."""
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if a file exists."""
        pass

    @abstractmethod
    async def list_files(self, prefix: str = "") -> List[str]:
        """List all files with the given prefix."""
        pass

    @abstractmethod
    async def delete_all(self, prefix: str = "") -> int:
        """Delete all files with the given prefix. Returns count of deleted files."""
        pass

    @abstractmethod
    def get_public_url(self, path: str) -> str:
        """Get the public URL for a file."""
        pass


class LocalStorage(StorageBackend):
    """Local filesystem storage for development."""

    def __init__(self, base_path: str = "/app/document_storage"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        log.info(f"📁 LocalStorage initialized at {self.base_path}")

    def _get_full_path(self, path: str) -> Path:
        """Get full filesystem path, ensuring it's within base_path."""
        full_path = self.base_path / path
        # Security: ensure path doesn't escape base_path
        full_path = full_path.resolve()
        if not str(full_path).startswith(str(self.base_path.resolve())):
            raise ValueError(f"Path {path} attempts to escape storage directory")
        return full_path

    async def upload(
        self,
        path: str,
        data: Union[bytes, BinaryIO],
        content_type: Optional[str] = None,
    ) -> str:
        full_path = self._get_full_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(data, bytes):
            full_path.write_bytes(data)
        else:
            full_path.write_bytes(data.read())

        log.debug(f"📤 Uploaded {path} to local storage")
        return self.get_public_url(path)

    async def download(self, path: str) -> bytes:
        full_path = self._get_full_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return full_path.read_bytes()

    async def delete(self, path: str) -> bool:
        full_path = self._get_full_path(path)
        if full_path.exists():
            full_path.unlink()
            log.debug(f"🗑️ Deleted {path} from local storage")
            return True
        return False

    async def exists(self, path: str) -> bool:
        full_path = self._get_full_path(path)
        return full_path.exists()

    async def list_files(self, prefix: str = "") -> List[str]:
        search_path = self._get_full_path(prefix) if prefix else self.base_path
        if not search_path.exists():
            return []

        files = []
        for item in search_path.rglob("*"):
            if item.is_file():
                relative_path = str(item.relative_to(self.base_path))
                files.append(relative_path)
        return files

    async def delete_all(self, prefix: str = "") -> int:
        files = await self.list_files(prefix)
        count = 0
        for file_path in files:
            if await self.delete(file_path):
                count += 1
        log.info(
            f"🗑️ Deleted {count} files from local storage (prefix: {prefix or 'all'})"
        )
        return count

    def get_public_url(self, path: str) -> str:
        # In local dev, return a relative path that can be served by the API
        base_path = os.getenv("BASE_PATH", "")
        return f"{base_path}/api/files/{path}"


class GCSStorage(StorageBackend):
    """Google Cloud Storage backend for production."""

    def __init__(self, bucket_name: str, prefix: str = ""):
        self.bucket_name = bucket_name
        self.prefix = prefix.strip("/")
        self._client = None
        self._bucket = None
        log.info(f"☁️ GCSStorage initialized for gs://{bucket_name}/{prefix}")

    @property
    def client(self):
        """Lazy initialization of GCS client."""
        if self._client is None:
            try:
                from google.cloud import storage

                self._client = storage.Client()
                self._bucket = self._client.bucket(self.bucket_name)
            except ImportError:
                raise ImportError(
                    "google-cloud-storage is required for GCS backend. "
                    "Install it with: pip install google-cloud-storage"
                )
        return self._client

    @property
    def bucket(self):
        """Get the GCS bucket."""
        if self._bucket is None:
            _ = self.client  # Initialize client
        return self._bucket

    def _get_blob_name(self, path: str) -> str:
        """Get full blob name with prefix."""
        if self.prefix:
            return f"{self.prefix}/{path}"
        return path

    async def upload(
        self,
        path: str,
        data: Union[bytes, BinaryIO],
        content_type: Optional[str] = None,
    ) -> str:
        blob_name = self._get_blob_name(path)
        blob = self.bucket.blob(blob_name)

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()

        if isinstance(data, bytes):
            await loop.run_in_executor(
                None, partial(blob.upload_from_string, data, content_type=content_type)
            )
        else:
            await loop.run_in_executor(
                None, partial(blob.upload_from_file, data, content_type=content_type)
            )

        log.debug(f"📤 Uploaded {path} to gs://{self.bucket_name}/{blob_name}")
        return self.get_public_url(path)

    async def download(self, path: str) -> bytes:
        blob_name = self._get_blob_name(path)
        blob = self.bucket.blob(blob_name)

        loop = asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, blob.download_as_bytes)
            return data
        except Exception as e:
            # GCS raises google.cloud.exceptions.NotFound when blob doesn't exist
            raise FileNotFoundError(f"File not found: {path}")

    async def delete(self, path: str) -> bool:
        blob_name = self._get_blob_name(path)
        blob = self.bucket.blob(blob_name)

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, blob.delete)
            log.debug(f"🗑️ Deleted gs://{self.bucket_name}/{blob_name}")
            return True
        except Exception:
            return False

    async def exists(self, path: str) -> bool:
        blob_name = self._get_blob_name(path)
        blob = self.bucket.blob(blob_name)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, blob.exists)

    async def list_files(self, prefix: str = "") -> List[str]:
        full_prefix = self._get_blob_name(prefix)

        loop = asyncio.get_event_loop()
        blobs = await loop.run_in_executor(
            None,
            partial(list, self.client.list_blobs(self.bucket_name, prefix=full_prefix)),
        )

        # Remove the storage prefix from returned paths
        files = []
        for blob in blobs:
            if self.prefix:
                relative_path = blob.name[len(self.prefix) + 1 :]
            else:
                relative_path = blob.name
            if relative_path:  # Skip empty paths (the prefix folder itself)
                files.append(relative_path)
        return files

    async def delete_all(self, prefix: str = "") -> int:
        full_prefix = self._get_blob_name(prefix)

        loop = asyncio.get_event_loop()
        blobs = await loop.run_in_executor(
            None,
            partial(list, self.client.list_blobs(self.bucket_name, prefix=full_prefix)),
        )

        count = 0
        for blob in blobs:
            try:
                await loop.run_in_executor(None, blob.delete)
                count += 1
            except Exception as e:
                log.warning(f"Failed to delete {blob.name}: {e}")

        log.info(f"🗑️ Deleted {count} files from gs://{self.bucket_name}/{full_prefix}")
        return count

    def get_public_url(self, path: str) -> str:
        blob_name = self._get_blob_name(path)
        # Return the GCS public URL (requires bucket to be public or use signed URLs)
        return f"https://storage.googleapis.com/{self.bucket_name}/{blob_name}"


def get_storage() -> StorageBackend:
    """
    Factory function to get the appropriate storage backend.

    Configuration via environment variables:
    - STORAGE_BACKEND: "local" or "gcs" (default: based on APP_ENV)
    - GCS_BUCKET: GCS bucket name (required for gcs backend)
    - GCS_PREFIX: Prefix/folder within the bucket (optional)
    - LOCAL_STORAGE_PATH: Local storage path (default: /app/document_storage)
    """
    app_env = os.getenv("APP_ENV", "development")
    storage_backend = os.getenv(
        "STORAGE_BACKEND", "gcs" if app_env == "production" else "local"
    )

    if storage_backend == "gcs":
        bucket_name = os.getenv("GCS_BUCKET")
        if not bucket_name:
            raise ValueError(
                "GCS_BUCKET environment variable is required for GCS storage"
            )
        prefix = os.getenv("GCS_PREFIX", "")
        return GCSStorage(bucket_name, prefix)
    else:
        local_path = os.getenv("LOCAL_STORAGE_PATH", "/app/document_storage")
        return LocalStorage(local_path)


# Global storage instance (lazy initialization)
_storage_instance: Optional[StorageBackend] = None


def get_storage_instance() -> StorageBackend:
    """Get or create the global storage instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = get_storage()
    return _storage_instance


# FastAPI dependency
def get_storage_dependency() -> StorageBackend:
    """FastAPI dependency for storage."""
    return get_storage_instance()
