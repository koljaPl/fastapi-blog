import os

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    ALGORITHM: str
    ADMIN_USERNAME: str
    ADMIN_PASSWORD: str
    DATABASE_URL: str
    PROJECT_NAME: str
    DEBUG: bool = False

    # Указываем Pydantic читать данные из файла .env
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()