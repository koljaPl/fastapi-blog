"""
Post schemas with detailed documentation.
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class PostBase(BaseModel):
    """Base post schema."""
    title: str = Field(..., min_length=3, max_length=200, description="Post title")
    content: str = Field(..., min_length=10, max_length=50000, description="Post content")
    excerpt: Optional[str] = Field(None, max_length=500, description="Short excerpt")
    published: bool = Field(default=False, description="Publication status")


class PostCreate(PostBase):
    """Schema for creating a post."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "My First Blog Post",
                "content": "This is the full content of my blog post...",
                "excerpt": "Short description of the post",
                "published": True
            }
        }
    )


class PostUpdate(BaseModel):
    """Schema for updating a post."""
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    content: Optional[str] = Field(None, min_length=10, max_length=50000)
    excerpt: Optional[str] = Field(None, max_length=500)
    published: Optional[bool] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Updated Title",
                "published": True
            }
        }
    )


class AuthorResponse(BaseModel):
    """Minimal author info."""
    id: int
    username: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PostResponse(BaseModel):
    """Schema for post in lists."""
    id: int
    title: str
    slug: str
    excerpt: Optional[str]
    published: bool
    views: int
    author_id: int
    author: AuthorResponse
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class PostDetailResponse(PostResponse):
    """Schema for detailed post view."""
    content: str = Field(..., description="Full post content")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "title": "My Blog Post",
                "slug": "my-blog-post",
                "content": "Full content here...",
                "excerpt": "Short excerpt",
                "published": True,
                "views": 42,
                "author_id": 1,
                "author": {
                    "id": 1,
                    "username": "john_doe",
                    "full_name": "John Doe"
                },
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T12:00:00"
            }
        }
    )


class PostListResponse(BaseModel):
    """Schema for paginated post list."""
    posts: List[PostResponse] = Field(..., description="List of posts")
    total: int = Field(..., description="Total number of posts")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Posts per page")
    has_more: bool = Field(..., description="Whether more posts available")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "posts": [],
                "total": 42,
                "page": 1,
                "page_size": 10,
                "has_more": True
            }
        }
    )