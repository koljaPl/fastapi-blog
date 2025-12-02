"""
Pydantic schemas for post validation and serialization.
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, validator


class PostBase(BaseModel):
    """Base post schema."""
    title: str = Field(..., min_length=3, max_length=200)
    content: str = Field(..., min_length=10, max_length=50000)
    excerpt: Optional[str] = Field(None, max_length=500)
    published: bool = False


class PostCreate(PostBase):
    """Schema for creating a post."""
    pass


class PostUpdate(BaseModel):
    """Schema for updating a post."""
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    content: Optional[str] = Field(None, min_length=10, max_length=50000)
    excerpt: Optional[str] = Field(None, max_length=500)
    published: Optional[bool] = None


class AuthorResponse(BaseModel):
    """Minimal author info for post responses."""
    id: int
    username: str
    full_name: Optional[str]
    avatar_url: Optional[str]

    class Config:
        from_attributes = True


class PostResponse(BaseModel):
    """Schema for post responses."""
    id: int
    title: str
    slug: str
    content: str
    excerpt: Optional[str]
    published: bool
    views: int
    author_id: int
    author: AuthorResponse
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class PostListResponse(BaseModel):
    """Schema for paginated post list."""
    posts: List[PostResponse]
    total: int
    page: int
    page_size: int
    has_more: bool