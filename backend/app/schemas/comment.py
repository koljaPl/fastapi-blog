"""
Comment schemas.
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class CommentBase(BaseModel):
    """Base comment schema."""
    content: str = Field(..., min_length=1, max_length=2000, description="Comment text")


class CommentCreate(CommentBase):
    """Schema for creating a comment."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content": "Great post! Thanks for sharing."
            }
        }
    )


class CommentUpdate(BaseModel):
    """Schema for updating a comment."""
    content: str = Field(..., min_length=1, max_length=2000, description="Updated comment text")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content": "Updated comment text"
            }
        }
    )


class CommentAuthor(BaseModel):
    """Comment author info."""
    id: int
    username: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CommentResponse(BaseModel):
    """Schema for comment response."""
    id: int
    content: str
    post_id: int
    author_id: int
    author: CommentAuthor
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "content": "Great post!",
                "post_id": 5,
                "author_id": 3,
                "author": {
                    "id": 3,
                    "username": "john_doe",
                    "full_name": "John Doe"
                },
                "created_at": "2024-01-15T10:30:00"
            }
        }
    )


class CommentListResponse(BaseModel):
    """Schema for paginated comment list."""
    comments: List[CommentResponse]
    total: int
    page: int
    page_size: int
    has_more: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "comments": [],
                "total": 15,
                "page": 1,
                "page_size": 10,
                "has_more": True
            }
        }
    )