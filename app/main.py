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


@app.get("/posts/{post_id}", tags=["Endpoints"], response_model=PostResponse)
async def read_post(post_id: int, db: AsyncSession = Depends(get_db)):
    # Используем scalars() для получения объектов
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with id {post_id} not found"
        )
    return post


@app.post("/posts/", tags=["Endpoints"], response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_new_post(post_data: PostCreate, db: AsyncSession = Depends(get_db)):
    new_post = Post(**post_data.model_dump())
    db.add(new_post)
    await db.commit()
    await db.refresh(new_post) # Загружаем сгенерированные БД поля (id, created_at)
    return new_post


@app.get("/posts/", tags=["Endpoints"], response_model=list[PostResponse])
async def read_posts(skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Post).offset(skip).limit(limit))
    return result.scalars().all()
