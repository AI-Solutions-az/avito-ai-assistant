import logging
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.routes import chat

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("uvicorn")

app = FastAPI()


class LogRequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        body = await request.body()
        logger.info(f"Request: {request.method} {request.url}")
        logger.info(f"Request body: {body.decode('utf-8')}")

        response = await call_next(request)
        logger.info(f"Response: {response.status_code} {request.url}")
        return response


# Добавление middleware в приложение
app.add_middleware(LogRequestMiddleware)

# Подключаем маршруты
app.include_router(chat.router, tags=["Chat"])


@app.get("/")
def read_root():
    return {"message": "AI Assistant is running!"}
