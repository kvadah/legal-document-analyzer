"""Object storage abstraction (S3/MinIO with local filesystem fallback)."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol

import aioboto3
from botocore.exceptions import ClientError

from app.core.config import settings


class StorageService(Protocol):
    async def ensure_bucket(self) -> None: ...
    async def put_bytes(self, key: str, data: bytes, content_type: str) -> str: ...
    async def get_bytes(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...


class LocalStorageService:
    """Filesystem storage for tests and local dev without MinIO."""

    def __init__(self, base_path: str) -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def ensure_bucket(self) -> None:
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def put_bytes(self, key: str, data: bytes, content_type: str) -> str:
        path = self.base_path / key
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)
        return key

    async def get_bytes(self, key: str) -> bytes:
        path = self.base_path / key
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, key: str) -> None:
        path = self.base_path / key
        if path.exists():
            await asyncio.to_thread(path.unlink)


class S3StorageService:
    """S3-compatible storage (MinIO in development)."""

    def __init__(self) -> None:
        self._session = aioboto3.Session()

    def _client_kwargs(self) -> dict:
        return {
            "service_name": "s3",
            "endpoint_url": settings.s3_endpoint_url,
            "aws_access_key_id": settings.s3_access_key,
            "aws_secret_access_key": settings.s3_secret_key,
            "region_name": settings.s3_region,
        }

    async def ensure_bucket(self) -> None:
        async with self._session.client(**self._client_kwargs()) as client:
            try:
                await client.head_bucket(Bucket=settings.s3_bucket_name)
            except ClientError:
                await client.create_bucket(Bucket=settings.s3_bucket_name)

    async def put_bytes(self, key: str, data: bytes, content_type: str) -> str:
        async with self._session.client(**self._client_kwargs()) as client:
            await client.put_object(
                Bucket=settings.s3_bucket_name,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        return key

    async def get_bytes(self, key: str) -> bytes:
        async with self._session.client(**self._client_kwargs()) as client:
            response = await client.get_object(Bucket=settings.s3_bucket_name, Key=key)
            body = await response["Body"].read()
            return body

    async def delete(self, key: str) -> None:
        async with self._session.client(**self._client_kwargs()) as client:
            await client.delete_object(Bucket=settings.s3_bucket_name, Key=key)


_storage: StorageService | None = None


def get_storage() -> StorageService:
    global _storage
    if _storage is None:
        if settings.storage_backend == "local":
            _storage = LocalStorageService(settings.local_storage_path)
        else:
            _storage = S3StorageService()
    return _storage


def reset_storage(storage: StorageService | None = None) -> None:
    """Reset the module-level storage singleton (used in tests)."""
    global _storage
    _storage = storage


def build_document_storage_key(org_id: str, document_id: str, suffix: str) -> str:
    return f"orgs/{org_id}/documents/{document_id}/{suffix}"
