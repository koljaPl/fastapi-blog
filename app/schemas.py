from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PostBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=100, description="Заголовок поста")
    content: str = Field(..., min_length=10, description="Основной текст поста")
    is_published: bool = True


# Схема для создания поста (то, что присылает клиент)
class PostCreate(PostBase):
    pass


# Схема для ответа API (то, что мы отдаем клиенту)
class PostResponse(PostBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    message: str


class Token(BaseModel):
    access_token: str
    token_type: str
