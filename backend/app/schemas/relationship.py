"""Pydantic schemas for document relationship endpoints (08 §2)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RelationshipTypeLiteral = Literal[
    "amendment", "exhibit", "related_agreement", "supersedes"
]


class RelationshipCreateRequest(BaseModel):
    related_document_id: str = Field(min_length=1)
    relationship_type: RelationshipTypeLiteral


class RelatedDocumentOut(BaseModel):
    """A single related-document entry on a document's relationship panel."""

    relationship_id: str
    direction: Literal["outgoing", "incoming"]
    relationship_type: RelationshipTypeLiteral
    other_document_id: str
    other_filename: str
    other_document_type: str
    other_status: str
    suggested: bool
    created_at: datetime


class RelationshipListResponse(BaseModel):
    document_id: str
    relationships: list[RelatedDocumentOut]


class RelationshipOut(BaseModel):
    id: str
    document_id_a: str
    document_id_b: str
    relationship_type: RelationshipTypeLiteral
    created_by: str | None = None
    created_at: datetime
