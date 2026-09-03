"""Chunk repository for document text segments."""
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Chunk


class ChunkRepository:
    """Repository for chunk persistence (scoped via document ownership checks upstream)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def delete_for_document(self, document_id: UUID) -> None:
        await self.session.execute(delete(Chunk).where(Chunk.document_id == document_id))
        await self.session.flush()

    async def list_for_document(self, document_id: UUID) -> list[Chunk]:
        stmt = (
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        self.session.add_all(chunks)
        await self.session.flush()
        for chunk in chunks:
            await self.session.refresh(chunk)
        return chunks
