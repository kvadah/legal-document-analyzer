"""Shared pytest fixtures."""
from __future__ import annotations

from pathlib import Path

import fakeredis.aioredis
import pytest
import pytest_asyncio
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.providers.embeddings import MockEmbeddingProvider, reset_embedding_provider
from app.services.storage_service import LocalStorageService, reset_storage
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
TestSessionLocal = sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False, future=True
)


@pytest.fixture(autouse=True)
def test_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_STORAGE_PATH", str(tmp_path / "storage"))
    monkeypatch.setenv("RUN_INGESTION_INLINE", "true")
    monkeypatch.setenv("MOCK_EMBEDDINGS", "true")
    settings.storage_backend = "local"
    settings.local_storage_path = str(tmp_path / "storage")
    settings.run_ingestion_inline = True
    settings.mock_embeddings = True
    reset_storage(LocalStorageService(settings.local_storage_path))
    reset_embedding_provider(MockEmbeddingProvider())
    yield


@pytest.fixture(autouse=True)
def pipeline_test_session(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.pipelines.ingestion.pipeline.AsyncSessionLocal", TestSessionLocal)


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch: pytest.MonkeyPatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def _get_redis():
        return fake

    monkeypatch.setattr("app.db.redis._redis_pool", fake)
    monkeypatch.setattr("app.db.redis.get_redis", _get_redis)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture()
async def db_session():
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture()
async def client(db_session):
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def register_user(client, *, org_name="Test Org", email="admin@example.com", password="password123"):
    return await client.post(
        "/api/v1/auth/register",
        json={"org_name": org_name, "email": email, "password": password},
    )
