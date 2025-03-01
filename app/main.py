from app.routes import chat
import logging
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn")
app = FastAPI()

class LogRequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Чтение тела запроса
        body = await request.body()

        # Логирование метода, URL и тела запроса
        logger.info(f"Request: {request.method} {request.url}")
        logger.info(f"Request body: {body.decode('utf-8')}")  # Декодируем байты в строку

        response = await call_next(request)
        return response

# Добавление middleware в приложение
app.add_middleware(LogRequestMiddleware)

# Подключаем маршруты
app.include_router(chat.router, tags=["Chat"])

@app.get("/")
def read_root():
    return {"message": "AI Assistant is running!"}
