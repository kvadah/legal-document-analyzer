"""Collaboration fields for comments and annotations (08-feature-spec-collaboration.md §5–6).

Comments gain threading (parent_comment_id) and review-workflow resolution
(resolved). Annotations gain the highlighted span text (highlight_text — used
to render the viewer overlay) and a user-chosen highlight color (color).

Revision ID: 007
Revises: 006
Create Date: 2026-09-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "comments",
        sa.Column(
            "parent_comment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("comments.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "comments",
        sa.Column("resolved", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_index(
        "ix_comments_parent_comment_id", "comments", ["parent_comment_id"]
    )

    op.add_column(
        "annotations",
        sa.Column("highlight_text", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "annotations",
        sa.Column(
            "color", sa.String(20), server_default="yellow", nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("annotations", "color")
    op.drop_column("annotations", "highlight_text")
    op.drop_index("ix_comments_parent_comment_id", table_name="comments")
    op.drop_column("comments", "resolved")
    op.drop_column("comments", "parent_comment_id")
