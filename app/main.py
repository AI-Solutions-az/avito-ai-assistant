from fastapi import FastAPI
from app.routes import chat

app = FastAPI()

# Подключаем маршруты
app.include_router(chat.router, prefix="/chat", tags=["Chat"])

@app.get("/")
def read_root():
    return {"message": "AI Assistant is running!"}

