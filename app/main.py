import uvicorn
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware

from app.routers import posts
from app.auth import verify_password, create_access_token, get_password_hash
from app.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

app.include_router(posts.router)

origins = [
    "http://localhost:3000",    # Твой фронтенд (React/Vue)
    "http://127.0.0.1:3000",
    # "https://myblog.com",     # Твой будущий домен в продакшене
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # Кому разрешаем доступ
    allow_credentials=True,
    allow_methods=["*"],              # Разрешаем все методы (GET, POST, PUT, DELETE)
    allow_headers=["*"],              # Разрешаем любые заголовки
)


@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != settings.ADMIN_USERNAME or \
            not verify_password(form_data.password, get_password_hash(settings.ADMIN_PASSWORD)):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access_token = create_access_token(data={"sub": form_data.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/", tags=["Root"])
async def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)