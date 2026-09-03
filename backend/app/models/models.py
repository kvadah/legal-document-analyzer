"""SQLAlchemy models for the Legal Document Analyzer."""
import enum
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    ARRAY,
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel


class Organization(BaseModel):
    """Organization tenant model."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="free", nullable=False)
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User", back_populates="organization", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="organization", cascade="all, delete-orphan"
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report", back_populates="organization", cascade="all, delete-orphan"
    )


class UserRole(str, enum.Enum):
    """User role enum."""

    ADMIN = "admin"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class User(BaseModel):
    """User model."""

    __tablename__ = "users"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=lambda x: [e.value for e in x]),
        default=UserRole.REVIEWER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_users_organization_id", "organization_id"),
        Index("ix_users_email", "email"),
    )

    # Relationships
    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="users"
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="user", cascade="all, delete-orphan"
    )
    annotations: Mapped[list["Annotation"]] = relationship(
        "Annotation", back_populates="user", cascade="all, delete-orphan"
    )
    uploaded_documents: Mapped[list["Document"]] = relationship(
        "Document", foreign_keys="Document.uploaded_by", back_populates="uploader"
    )


class DocumentStatus(str, enum.Enum):
    """Document processing status enum."""

    UPLOADED = "uploaded"
    OCR_PROCESSING = "ocr_processing"
    OCR_COMPLETE = "ocr_complete"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    METADATA_EXTRACTION = "metadata_extraction"
    INGESTION_READY = "ingestion_ready"
    AI_PIPELINE_PROCESSING = "ai_pipeline_processing"
    ANALYSIS_READY = "analysis_ready"
    ERROR = "error"


class DocumentType(str, enum.Enum):
    """Document type enum."""

    CONTRACT = "contract"
    NDA = "nda"
    EMPLOYMENT_AGREEMENT = "employment_agreement"
    LEASE = "lease"
    PROCUREMENT = "procurement"
    INSURANCE = "insurance"
    GOVERNMENT_FORM = "government_form"
    POLICY = "policy"
    TOS = "tos"
    OTHER = "other"


class Document(BaseModel):
    """Document model."""

    __tablename__ = "documents"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    ocr_text_storage_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, values_callable=lambda x: [e.value for e in x]),
        default=DocumentType.OTHER,
        nullable=False,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, values_callable=lambda x: [e.value for e in x]),
        default=DocumentStatus.UPLOADED,
        nullable=False,
    )
    status_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    contract_score: Mapped[float | None] = mapped_column(Numeric(3, 1), nullable=True)
    ai_confidence_score: Mapped[float | None] = mapped_column(
        Numeric(3, 2), nullable=True
    )
    parent_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    __table_args__ = (
        Index("ix_documents_organization_id", "organization_id"),
        Index("ix_documents_uploaded_by", "uploaded_by"),
        Index("ix_documents_status", "status"),
        Index("ix_documents_created_at", "created_at"),
    )

    # Relationships
    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="documents"
    )
    uploader: Mapped[User] = relationship(
        "User", foreign_keys=[uploaded_by], back_populates="uploaded_documents"
    )
    versions: Mapped[list["DocumentVersion"]] = relationship(
        "DocumentVersion", back_populates="document", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )
    clauses: Mapped[list["Clause"]] = relationship(
        "Clause", back_populates="document", cascade="all, delete-orphan"
    )
    risks: Mapped[list["Risk"]] = relationship(
        "Risk", back_populates="document", cascade="all, delete-orphan"
    )
    entities: Mapped[list["Entity"]] = relationship(
        "Entity", back_populates="document", cascade="all, delete-orphan"
    )
    obligations: Mapped[list["Obligation"]] = relationship(
        "Obligation", back_populates="document", cascade="all, delete-orphan"
    )
    summary: Mapped[Optional["DocumentSummary"]] = relationship(
        "DocumentSummary", back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="document", cascade="all, delete-orphan"
    )
    annotations: Mapped[list["Annotation"]] = relationship(
        "Annotation", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentVersion(BaseModel):
    """Document version model."""

    __tablename__ = "document_versions"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_document_versions_document_id", "document_id"),
        UniqueConstraint("document_id", "version_number", name="uq_doc_version"),
    )

    # Relationships
    document: Mapped[Document] = relationship("Document", back_populates="versions")


class Chunk(BaseModel):
    """Document chunk model."""

    __tablename__ = "chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    paragraph_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_vector_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_chunks_document_id", "document_id"),
        Index("ix_chunks_page_number", "page_number"),
    )

    # Relationships
    document: Mapped[Document] = relationship("Document", back_populates="chunks")


class ClauseType(str, enum.Enum):
    """Clause type enum."""

    TERMINATION = "termination"
    CONFIDENTIALITY = "confidentiality"
    INDEMNIFICATION = "indemnification"
    LIABILITY = "liability"
    ARBITRATION = "arbitration"
    PAYMENT = "payment"
    IP = "ip"
    JURISDICTION = "jurisdiction"
    RENEWAL = "renewal"
    FORCE_MAJEURE = "force_majeure"


class UUIDListJSON(TypeDecorator):
    """JSON storage of a UUID list for SQLite (tests); Postgres uses native ARRAY(UUID)."""

    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return [str(v) if isinstance(v, uuid.UUID) else v for v in value]

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return [uuid.UUID(v) if isinstance(v, str) else v for v in value]


class Clause(BaseModel):
    """Clause model."""

    __tablename__ = "clauses"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    clause_type: Mapped[ClauseType] = mapped_column(
        Enum(ClauseType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    paragraph_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    source_chunk_ids: Mapped[list | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)).with_variant(UUIDListJSON(), "sqlite"), nullable=True
    )

    __table_args__ = (
        Index("ix_clauses_document_id", "document_id"),
        Index("ix_clauses_clause_type", "clause_type"),
    )

    # Relationships
    document: Mapped[Document] = relationship("Document", back_populates="clauses")
    risks: Mapped[list["Risk"]] = relationship(
        "Risk", back_populates="clause", cascade="all, delete-orphan"
    )


class RiskType(str, enum.Enum):
    """Risk type enum."""

    UNLIMITED_LIABILITY = "unlimited_liability"
    MISSING_NDA = "missing_nda"
    MISSING_TERMINATION = "missing_termination"
    AMBIGUOUS_LANGUAGE = "ambiguous_language"
    NO_GOVERNING_LAW = "no_governing_law"
    AUTO_RENEWAL = "auto_renewal"
    HIGH_PENALTY = "high_penalty"
    OTHER = "other"


class RiskSeverity(str, enum.Enum):
    """Risk severity enum."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskStatus(str, enum.Enum):
    """Risk status enum."""

    FLAGGED = "flagged"
    ACKNOWLEDGED = "acknowledged"
    DISMISSED = "dismissed"


class Risk(BaseModel):
    """Risk model."""

    __tablename__ = "risks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    clause_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clauses.id"), nullable=True
    )
    risk_type: Mapped[RiskType] = mapped_column(
        Enum(RiskType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    severity: Mapped[RiskSeverity] = mapped_column(
        Enum(RiskSeverity, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    status: Mapped[RiskStatus] = mapped_column(
        Enum(RiskStatus, values_callable=lambda x: [e.value for e in x]),
        default=RiskStatus.FLAGGED,
        nullable=False,
    )

    __table_args__ = (
        Index("ix_risks_document_id", "document_id"),
        Index("ix_risks_clause_id", "clause_id"),
        Index("ix_risks_severity", "severity"),
    )

    # Relationships
    document: Mapped[Document] = relationship("Document", back_populates="risks")
    clause: Mapped[Clause | None] = relationship("Clause", back_populates="risks")


class EntityType(str, enum.Enum):
    """Entity type enum."""

    COMPANY = "company"
    PERSON = "person"
    MONEY = "money"
    DATE = "date"
    ADDRESS = "address"
    LAW_REFERENCE = "law_reference"


class Entity(BaseModel):
    """Entity model."""

    __tablename__ = "entities"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    entity_type: Mapped[EntityType] = mapped_column(
        Enum(EntityType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    value: Mapped[str] = mapped_column(String(512), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)

    __table_args__ = (
        Index("ix_entities_document_id", "document_id"),
        Index("ix_entities_entity_type", "entity_type"),
    )

    # Relationships
    document: Mapped[Document] = relationship("Document", back_populates="entities")


class DeadlineType(str, enum.Enum):
    """Deadline type enum."""

    EFFECTIVE_DATE = "effective_date"
    PAYMENT_DATE = "payment_date"
    RENEWAL_DATE = "renewal_date"
    NOTICE_PERIOD = "notice_period"
    EXPIRATION_DATE = "expiration_date"
    OTHER = "other"


class ObligationStatus(str, enum.Enum):
    """Obligation status enum."""

    UPCOMING = "upcoming"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    COMPLETED = "completed"


class Obligation(BaseModel):
    """Obligation model."""

    __tablename__ = "obligations"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    obligated_party: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    deadline_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deadline_type: Mapped[DeadlineType] = mapped_column(
        Enum(DeadlineType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    penalty_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_clause_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clauses.id"), nullable=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ObligationStatus] = mapped_column(
        Enum(ObligationStatus, values_callable=lambda x: [e.value for e in x]),
        default=ObligationStatus.UPCOMING,
        nullable=False,
    )

    __table_args__ = (
        Index("ix_obligations_document_id", "document_id"),
        Index("ix_obligations_deadline_date", "deadline_date"),
    )

    # Relationships
    document: Mapped[Document] = relationship("Document", back_populates="obligations")


class DocumentSummary(BaseModel):
    """Document summary model."""

    __tablename__ = "document_summaries"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), unique=True, nullable=False
    )
    parties: Mapped[str | None] = mapped_column(Text, nullable=True)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[str | None] = mapped_column(Text, nullable=True)
    termination_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_risks: Mapped[str | None] = mapped_column(Text, nullable=True)
    financial_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    governing_law: Mapped[str | None] = mapped_column(String(255), nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_value: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    contract_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    source_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (Index("ix_document_summaries_document_id", "document_id"),)

    # Relationships
    document: Mapped[Document] = relationship("Document", back_populates="summary")


class Comment(BaseModel):
    """Comment model."""

    __tablename__ = "comments"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paragraph_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_comments_document_id", "document_id"),
        Index("ix_comments_user_id", "user_id"),
    )

    # Relationships
    document: Mapped[Document] = relationship("Document", back_populates="comments")
    user: Mapped[User] = relationship("User", back_populates="comments")


class Annotation(BaseModel):
    """Annotation model."""

    __tablename__ = "annotations"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    annotation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    paragraph_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_annotations_document_id", "document_id"),
        Index("ix_annotations_user_id", "user_id"),
    )

    # Relationships
    document: Mapped[Document] = relationship("Document", back_populates="annotations")
    user: Mapped[User] = relationship("User", back_populates="annotations")


class Comparison(BaseModel):
    """Document comparison model."""

    __tablename__ = "comparisons"

    document_id_a: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    document_id_b: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_comparisons_document_id_a", "document_id_a"),
        Index("ix_comparisons_document_id_b", "document_id_b"),
    )


class Report(BaseModel):
    """Report model."""

    __tablename__ = "reports"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    download_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    __table_args__ = (
        Index("ix_reports_organization_id", "organization_id"),
        Index("ix_reports_report_type", "report_type"),
    )

    # Relationships
    organization: Mapped[Organization] = relationship("Organization", back_populates="reports")
