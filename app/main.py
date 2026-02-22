from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.schemas import PostCreate, PostResponse
from app.database import async_session, Post

app = FastAPI(title="My Best Practice Blog")

async def get_db():
    async with async_session() as session:
        yield session

@app.get("/", tags=["Root"])
async def root():
    return {"message": "Hello World"}

@app.get("/posts/{post_id}", response_model=PostResponse)
async def read_post(post_id: int, db: AsyncSession = Depends(get_db)):
    # Правильный асинхронный запрос через SQLAlchemy 2.0
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()

    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@app.post("/posts/", response_model=PostResponse)
async def create_new_post(post_data: PostCreate, db: AsyncSession = Depends(get_db)):
    new_post = Post(**post_data.model_dump())
    db.add(new_post)
    await db.commit()
    await db.refresh(new_post)
    return new_post
