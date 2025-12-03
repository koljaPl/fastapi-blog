"""
User schemas with complete documentation.
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
import re


class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    full_name: Optional[str] = Field(None, max_length=100, description="Full name")


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    full_name: Optional[str] = Field(None, max_length=100, description="Full name")
    bio: Optional[str] = Field(None, max_length=500, description="User biography")
    avatar_url: Optional[str] = Field(None, max_length=255, description="Avatar image URL")

    @field_validator('avatar_url')
    def validate_avatar_url(cls, v):
        """Validate avatar URL format."""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('Avatar URL must start with http:// or https://')
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "John Doe",
                "bio": "Software developer and blogger",
                "avatar_url": "https://example.com/avatar.jpg"
            }
        }
    )


class UserResponse(BaseModel):
    """Basic user response."""
    id: int
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserDetailResponse(UserResponse):
    """Detailed user response with all fields."""
    bio: Optional[str] = None
    is_superuser: bool
    last_login: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "email": "user@example.com",
                "username": "john_doe",
                "full_name": "John Doe",
                "bio": "Software developer",
                "avatar_url": "https://example.com/avatar.jpg",
                "is_active": True,
                "is_superuser": False,
                "created_at": "2024-01-15T10:30:00",
                "last_login": "2024-01-20T15:45:00"
            }
        }
    )


class UserListResponse(BaseModel):
    """Schema for paginated user list."""
    users: List[UserResponse]
    total: int
    page: int
    page_size: int
    has_more: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "users": [],
                "total": 25,
                "page": 1,
                "page_size": 10,
                "has_more": True
            }
        }
    )