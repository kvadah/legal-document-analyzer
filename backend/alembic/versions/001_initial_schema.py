"""Initial migration creating all tables.

Revision ID: 001
Revises: 
Create Date: 2026-08-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Create enums
    userole_enum = postgresql.ENUM(
        "admin", "reviewer", "viewer", name="userrole", create_type=False
    )
    userole_enum.create(op.get_bind(), checkfirst=True)

    documentstatus_enum = postgresql.ENUM(
        "uploaded",
        "ocr_processing",
        "ocr_complete",
        "parsing",
        "chunking",
        "embedding",
        "metadata_extraction",
        "ingestion_ready",
        "ai_pipeline_processing",
        "analysis_ready",
        "error",
        name="documentstatus",
        create_type=False,
    )
    documentstatus_enum.create(op.get_bind(), checkfirst=True)

    documenttype_enum = postgresql.ENUM(
        "contract",
        "nda",
        "employment_agreement",
        "lease",
        "procurement",
        "insurance",
        "government_form",
        "policy",
        "tos",
        "other",
        name="documenttype",
        create_type=False,
    )
    documenttype_enum.create(op.get_bind(), checkfirst=True)

    clausetype_enum = postgresql.ENUM(
        "termination",
        "confidentiality",
        "indemnification",
        "liability",
        "arbitration",
        "payment",
        "ip",
        "jurisdiction",
        "renewal",
        "force_majeure",
        name="clausetype",
        create_type=False,
    )
    clausetype_enum.create(op.get_bind(), checkfirst=True)

    risktype_enum = postgresql.ENUM(
        "unlimited_liability",
        "missing_nda",
        "missing_termination",
        "ambiguous_language",
        "no_governing_law",
        "auto_renewal",
        "high_penalty",
        "other",
        name="risktype",
        create_type=False,
    )
    risktype_enum.create(op.get_bind(), checkfirst=True)

    riskseverity_enum = postgresql.ENUM(
        "low", "medium", "high", "critical", name="riskseverity", create_type=False
    )
    riskseverity_enum.create(op.get_bind(), checkfirst=True)

    riskstatus_enum = postgresql.ENUM(
        "flagged", "acknowledged", "dismissed", name="riskstatus", create_type=False
    )
    riskstatus_enum.create(op.get_bind(), checkfirst=True)

    entitytype_enum = postgresql.ENUM(
        "company",
        "person",
        "money",
        "date",
        "address",
        "law_reference",
        name="entitytype",
        create_type=False,
    )
    entitytype_enum.create(op.get_bind(), checkfirst=True)

    deadlinetype_enum = postgresql.ENUM(
        "effective_date",
        "payment_date",
        "renewal_date",
        "notice_period",
        "expiration_date",
        "other",
        name="deadlinetype",
        create_type=False,
    )
    deadlinetype_enum.create(op.get_bind(), checkfirst=True)

    obligationstatus_enum = postgresql.ENUM(
        "upcoming",
        "due_soon",
        "overdue",
        "completed",
        name="obligationstatus",
        create_type=False,
    )
    obligationstatus_enum.create(op.get_bind(), checkfirst=True)

    # Create organizations table
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("plan", sa.String(50), nullable=False, server_default="free"),
        sa.Column("settings", postgresql.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("role", userole_enum, nullable=False, server_default="reviewer"),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_index("ix_users_email", "users", ["email"])

    # Create documents table
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_path", sa.String(512), nullable=False),
        sa.Column("ocr_text_storage_path", sa.String(512), nullable=True),
        sa.Column(
            "document_type",
            documenttype_enum,
            nullable=False,
            server_default="other",
        ),
        sa.Column(
            "status",
            documentstatus_enum,
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column("status_detail", sa.Text(), nullable=True),
        sa.Column("contract_score", sa.Numeric(precision=3, scale=1), nullable=True),
        sa.Column(
            "ai_confidence_score",
            sa.Numeric(precision=3, scale=2),
            nullable=True,
        ),
        sa.Column("parent_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["parent_document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_organization_id", "documents", ["organization_id"])
    op.create_index("ix_documents_uploaded_by", "documents", ["uploaded_by"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_created_at", "documents", ["created_at"])

    # Create document_versions table
    op.create_table(
        "document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(512), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "version_number", name="uq_doc_version"),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])

    # Create chunks table
    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("paragraph_index", sa.Integer(), nullable=True),
        sa.Column("section_heading", sa.Text(), nullable=True),
        sa.Column("embedding_vector_id", sa.String(255), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_page_number", "chunks", ["page_number"])

    # Create clauses table
    op.create_table(
        "clauses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clause_type", clausetype_enum, nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("paragraph_index", sa.Integer(), nullable=True),
        sa.Column(
            "confidence_score", sa.Numeric(precision=3, scale=2), nullable=True
        ),
        sa.Column(
            "source_chunk_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clauses_document_id", "clauses", ["document_id"])
    op.create_index("ix_clauses_clause_type", "clauses", ["clause_type"])

    # Create risks table
    op.create_table(
        "risks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clause_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("risk_type", risktype_enum, nullable=False),
        sa.Column("severity", riskseverity_enum, nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column(
            "confidence_score", sa.Numeric(precision=3, scale=2), nullable=True
        ),
        sa.Column(
            "status", riskstatus_enum, nullable=False, server_default="flagged"
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["clause_id"], ["clauses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_risks_document_id", "risks", ["document_id"])
    op.create_index("ix_risks_clause_id", "risks", ["clause_id"])
    op.create_index("ix_risks_severity", "risks", ["severity"])

    # Create entities table
    op.create_table(
        "entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", entitytype_enum, nullable=False),
        sa.Column("value", sa.String(512), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column(
            "confidence_score", sa.Numeric(precision=3, scale=2), nullable=True
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entities_document_id", "entities", ["document_id"])
    op.create_index("ix_entities_entity_type", "entities", ["entity_type"])

    # Create obligations table
    op.create_table(
        "obligations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("obligated_party", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("deadline_date", sa.DateTime(), nullable=True),
        sa.Column("deadline_type", deadlinetype_enum, nullable=False),
        sa.Column("penalty_description", sa.Text(), nullable=True),
        sa.Column("source_clause_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column(
            "status", obligationstatus_enum, nullable=False, server_default="upcoming"
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["source_clause_id"], ["clauses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_obligations_document_id", "obligations", ["document_id"])
    op.create_index("ix_obligations_deadline_date", "obligations", ["deadline_date"])

    # Create document_summaries table
    op.create_table(
        "document_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parties", sa.Text(), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("duration", sa.Text(), nullable=True),
        sa.Column("termination_conditions", sa.Text(), nullable=True),
        sa.Column("key_risks", sa.Text(), nullable=True),
        sa.Column("financial_terms", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id"),
    )
    op.create_index("ix_document_summaries_document_id", "document_summaries", ["document_id"])

    # Create comments table
    op.create_table(
        "comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("paragraph_index", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comments_document_id", "comments", ["document_id"])
    op.create_index("ix_comments_user_id", "comments", ["user_id"])

    # Create annotations table
    op.create_table(
        "annotations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("annotation_type", sa.String(50), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("paragraph_index", sa.Integer(), nullable=True),
        sa.Column("start_offset", sa.Integer(), nullable=True),
        sa.Column("end_offset", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_annotations_document_id", "annotations", ["document_id"])
    op.create_index("ix_annotations_user_id", "annotations", ["user_id"])

    # Create comparisons table
    op.create_table(
        "comparisons",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document_id_a", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id_b", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("result", postgresql.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["document_id_a"], ["documents.id"]),
        sa.ForeignKeyConstraint(["document_id_b"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comparisons_document_id_a", "comparisons", ["document_id_a"])
    op.create_index("ix_comparisons_document_id_b", "comparisons", ["document_id_b"])

    # Create reports table
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("data", postgresql.JSON(), nullable=True),
        sa.Column("download_url", sa.String(512), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reports_organization_id", "reports", ["organization_id"])
    op.create_index("ix_reports_report_type", "reports", ["report_type"])


def downgrade() -> None:
    """Downgrade database schema."""
    # Drop all tables in reverse order of creation
    op.drop_table("reports")
    op.drop_table("comparisons")
    op.drop_table("annotations")
    op.drop_table("comments")
    op.drop_table("document_summaries")
    op.drop_table("obligations")
    op.drop_table("entities")
    op.drop_table("risks")
    op.drop_table("clauses")
    op.drop_table("chunks")
    op.drop_table("document_versions")
    op.drop_table("documents")
    op.drop_table("users")
    op.drop_table("organizations")

    # Drop enums
    sa.Enum(
        "admin", "reviewer", "viewer", name="userrole"
    ).drop(op.get_bind(), checkfirst=True)
    sa.Enum(
        "uploaded",
        "ocr_processing",
        "ocr_complete",
        "parsing",
        "chunking",
        "embedding",
        "metadata_extraction",
        "ingestion_ready",
        "ai_pipeline_processing",
        "analysis_ready",
        "error",
        name="documentstatus",
    ).drop(op.get_bind(), checkfirst=True)
    sa.Enum(
        "contract",
        "nda",
        "employment_agreement",
        "lease",
        "procurement",
        "insurance",
        "government_form",
        "policy",
        "tos",
        "other",
        name="documenttype",
    ).drop(op.get_bind(), checkfirst=True)
    sa.Enum(
        "termination",
        "confidentiality",
        "indemnification",
        "liability",
        "arbitration",
        "payment",
        "ip",
        "jurisdiction",
        "renewal",
        "force_majeure",
        name="clausetype",
    ).drop(op.get_bind(), checkfirst=True)
    sa.Enum(
        "unlimited_liability",
        "missing_nda",
        "missing_termination",
        "ambiguous_language",
        "no_governing_law",
        "auto_renewal",
        "high_penalty",
        "other",
        name="risktype",
    ).drop(op.get_bind(), checkfirst=True)
    sa.Enum(
        "low", "medium", "high", "critical", name="riskseverity"
    ).drop(op.get_bind(), checkfirst=True)
    sa.Enum(
        "flagged", "acknowledged", "dismissed", name="riskstatus"
    ).drop(op.get_bind(), checkfirst=True)
    sa.Enum(
        "company",
        "person",
        "money",
        "date",
        "address",
        "law_reference",
        name="entitytype",
    ).drop(op.get_bind(), checkfirst=True)
    sa.Enum(
        "effective_date",
        "payment_date",
        "renewal_date",
        "notice_period",
        "expiration_date",
        "other",
        name="deadlinetype",
    ).drop(op.get_bind(), checkfirst=True)
    sa.Enum(
        "upcoming",
        "due_soon",
        "overdue",
        "completed",
        name="obligationstatus",
    ).drop(op.get_bind(), checkfirst=True)
