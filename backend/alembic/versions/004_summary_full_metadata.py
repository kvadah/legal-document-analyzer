"""Add full metadata columns to document_summaries.

Revision ID: 004
Revises: 003
Create Date: 2026-09-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    summaries = "document_summaries"
    op.add_column(summaries, sa.Column("governing_law", sa.String(length=255), nullable=True))
    op.add_column(summaries, sa.Column("effective_date", sa.Date(), nullable=True))
    op.add_column(summaries, sa.Column("expiration_date", sa.Date(), nullable=True))
    op.add_column(summaries, sa.Column("contract_value", sa.Numeric(15, 2), nullable=True))
    op.add_column(summaries, sa.Column("contract_currency", sa.String(length=3), nullable=True))
    op.add_column(summaries, sa.Column("source_data", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("document_summaries", "source_data")
    op.drop_column("document_summaries", "contract_currency")
    op.drop_column("document_summaries", "contract_value")
    op.drop_column("document_summaries", "expiration_date")
    op.drop_column("document_summaries", "effective_date")
    op.drop_column("document_summaries", "governing_law")
