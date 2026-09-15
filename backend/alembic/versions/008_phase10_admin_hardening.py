"""Phase 10 administration & hardening (11-security-compliance.md §6–7, 09-api-spec.md §9).

Adds the append-only audit log, LLM token usage telemetry, document
soft-delete (deleted_at), and org-level retention/deletion settings.

Revision ID: 008
Revises: 007
Create Date: 2026-09-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Organizations: retention policy + deletion scheduling ──────────────
    op.add_column(
        "organizations",
        sa.Column("retention_days", sa.Integer(), server_default="30", nullable=False),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "audit_retention_days", sa.Integer(), server_default="730", nullable=False
        ),
    )
    op.add_column("organizations", sa.Column("llm_provider", sa.String(50), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("scheduled_deletion_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── Documents: soft delete ─────────────────────────────────────────────
    op.add_column("documents", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_documents_deleted_at", "documents", ["deleted_at"])

    # ── Audit logs (append-only) ───────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_audit_logs_organization_id", "audit_logs", ["organization_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])

    # ── LLM usage telemetry ────────────────────────────────────────────────
    op.create_table(
        "llm_usage_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id"),
            nullable=True,
        ),
        sa.Column("stage", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=True),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_llm_usage_logs_organization_id", "llm_usage_logs", ["organization_id"])
    op.create_index("ix_llm_usage_logs_created_at", "llm_usage_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("llm_usage_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_documents_deleted_at", table_name="documents")
    op.drop_column("documents", "deleted_at")
    op.drop_column("organizations", "scheduled_deletion_at")
    op.drop_column("organizations", "llm_provider")
    op.drop_column("organizations", "audit_retention_days")
    op.drop_column("organizations", "retention_days")
