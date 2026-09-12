"""Extend reports table for report generation (08-feature-spec-collaboration.md §7).

Adds generated_by, document_ids, export_format, storage_path, error to the
reports table; drops the unused download_url column (downloads are served
through the authenticated API rather than presigned URLs).

Revision ID: 006
Revises: 005
Create Date: 2026-09-12
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reports",
        sa.Column(
            "generated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "reports",
        sa.Column("document_ids", postgresql.JSON(), nullable=True),
    )
    op.add_column(
        "reports",
        sa.Column("export_format", sa.String(10), nullable=False, server_default="json"),
    )
    op.add_column(
        "reports",
        sa.Column("storage_path", sa.String(512), nullable=True),
    )
    op.add_column(
        "reports",
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.drop_column("reports", "download_url")
    op.create_index("ix_reports_generated_by", "reports", ["generated_by"])


def downgrade() -> None:
    op.drop_index("ix_reports_generated_by", table_name="reports")
    op.drop_column("reports", "error")
    op.drop_column("reports", "storage_path")
    op.drop_column("reports", "export_format")
    op.drop_column("reports", "document_ids")
    op.drop_column("reports", "generated_by")
    op.add_column(
        "reports",
        sa.Column("download_url", sa.String(512), nullable=True),
    )
