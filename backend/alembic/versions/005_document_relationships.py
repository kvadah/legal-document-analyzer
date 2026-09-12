"""Add document_relationships table and parent_document_id index.

Revision ID: 005
Revises: 004
Create Date: 2026-09-11
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    relationshiptype_enum = postgresql.ENUM(
        "amendment",
        "exhibit",
        "related_agreement",
        "supersedes",
        name="relationshiptype",
        create_type=False,
    )
    relationshiptype_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "document_relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "document_id_a",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id"),
            nullable=False,
        ),
        sa.Column(
            "document_id_b",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id"),
            nullable=False,
        ),
        sa.Column("relationship_type", relationshiptype_enum, nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id_a", "document_id_b", "relationship_type", name="uq_doc_relationship"
        ),
    )
    op.create_index(
        "ix_document_relationships_a", "document_relationships", ["document_id_a"]
    )
    op.create_index(
        "ix_document_relationships_b", "document_relationships", ["document_id_b"]
    )

    op.create_index(
        "ix_documents_parent_document_id", "documents", ["parent_document_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_documents_parent_document_id", table_name="documents")
    op.drop_index("ix_document_relationships_b", table_name="document_relationships")
    op.drop_index("ix_document_relationships_a", table_name="document_relationships")
    op.drop_table("document_relationships")
    relationshiptype_enum = postgresql.ENUM(
        "amendment",
        "exhibit",
        "related_agreement",
        "supersedes",
        name="relationshiptype",
        create_type=False,
    )
    relationshiptype_enum.drop(op.get_bind(), checkfirst=True)
