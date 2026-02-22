from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional

class PostBase(BaseModel):
    title: str
    content: str
    is_published: bool = True

    model_config = ConfigDict(from_attributes=True)  # Позволяет Pydantic читать данные из SQLAlchemy моделей

# Схема для создания поста (то, что присылает клиент)
class PostCreate(PostBase):
    pass

# Схема для ответа API (то, что мы отдаем клиенту)
class PostResponse(PostBase):
    id: int
    created_at: datetime
