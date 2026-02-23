from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.config import settings
from app.database import Post, async_session

router = APIRouter(prefix="/posts", tags=["Posts"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# Dependency для БД (теперь она живет здесь или в отдельном файле dependencies.py)
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username = payload.get("sub")
        if not isinstance(username, str) or username != settings.ADMIN_USERNAME:
            raise credentials_exception

        if username is None or username != settings.ADMIN_USERNAME:
            raise credentials_exception from None

    except JWTError:
        raise credentials_exception from None
    return username


@router.get("/{post_id}", response_model=schemas.PostResponse)
async def read_post(post_id: int, db: AsyncSession = Depends(get_db)) -> Post:
    post = await crud.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.post(
    "/", response_model=schemas.PostResponse, status_code=status.HTTP_201_CREATED
)
async def create_post(
    post_data: schemas.PostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),  # Вот наш замок!
) -> Post:
    return await crud.create_post(db, post_data)


@router.put("/{post_id}", response_model=schemas.PostResponse)
async def update_post(
    post_id: int, updated_data: schemas.PostCreate, db: AsyncSession = Depends(get_db)
) -> Post:
    post = await crud.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return await crud.update_post(db, post, updated_data)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    post = await crud.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    await crud.delete_post(db, post)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/", response_model=list[schemas.PostResponse])
async def read_posts(
    skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)
) -> list[Post]:
    posts = await crud.get_posts(db, skip=skip, limit=limit)
    return list(posts)
