from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import Post
from app.schemas import PostCreate

async def get_post(db: AsyncSession, post_id: int):
    result = await db.execute(select(Post).where(Post.id == post_id))
    return result.scalar_one_or_none()

async def create_post(db: AsyncSession, post_data: PostCreate):
    new_post = Post(**post_data.model_dump())
    db.add(new_post)
    await db.commit()
    await db.refresh(new_post)
    return new_post

async def update_post(db: AsyncSession, post: Post, updated_data: PostCreate):
    post_dict = updated_data.model_dump()
    for key, value in post_dict.items():
        setattr(post, key, value)
    await db.commit()
    await db.refresh(post)
    return post

async def delete_post(db: AsyncSession, post: Post):
    await db.delete(post)
    await db.commit()

async def get_posts(db: AsyncSession, skip: int = 0, limit: int = 10):
    result = await db.execute(select(Post).offset(skip).limit(limit))
    return result.scalars().all()
