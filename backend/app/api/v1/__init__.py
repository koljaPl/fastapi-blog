"""
API v1 router initialization.
Aggregates all v1 endpoints.
"""
from fastapi import APIRouter

from app.api.v1 import auth, posts, users, comments

api_router = APIRouter()

# Include all v1 routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(posts.router, prefix="/posts", tags=["Posts"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(comments.router, prefix="/comments", tags=["Comments"])