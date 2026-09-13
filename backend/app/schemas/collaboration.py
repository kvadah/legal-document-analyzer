"""Pydantic schemas for collaboration endpoints (08-feature-spec-collaboration.md §5–6)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# User-configurable highlight palette (validated server-side so the viewer
# only ever receives colors it can render).
ANNOTATION_COLORS = ("yellow", "green", "blue", "red", "purple")


class CommentCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    page_number: int | None = Field(default=None, ge=1)
    parent_comment_id: str | None = None


class CommentUpdateRequest(BaseModel):
    """Content edits are author-only; `resolved` toggling is the review
    workflow and available to any reviewer/admin (08 §5)."""

    content: str | None = Field(default=None, min_length=1, max_length=5000)
    resolved: bool | None = None


class CommentOut(BaseModel):
    id: str
    document_id: str
    user_id: str
    author_email: str
    author_name: str | None = None
    content: str
    page_number: int | None = None
    parent_comment_id: str | None = None
    resolved: bool
    created_at: datetime
    updated_at: datetime


class CommentListResponse(BaseModel):
    document_id: str
    comments: list[CommentOut]
    total: int


class AnnotationCreateRequest(BaseModel):
    highlight_text: str = Field(min_length=1, max_length=2000)
    content: str = Field(default="", max_length=2000)
    color: str = Field(default="yellow", pattern="^(yellow|green|blue|red|purple)$")
    page_number: int = Field(ge=1)
    paragraph_index: int | None = Field(default=None, ge=0)
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)


class AnnotationUpdateRequest(BaseModel):
    content: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(
        default=None, pattern="^(yellow|green|blue|red|purple)$"
    )


class AnnotationOut(BaseModel):
    id: str
    document_id: str
    user_id: str
    author_email: str
    author_name: str | None = None
    content: str
    highlight_text: str
    color: str
    page_number: int
    created_at: datetime
    updated_at: datetime


class AnnotationListResponse(BaseModel):
    document_id: str
    annotations: list[AnnotationOut]
    total: int
