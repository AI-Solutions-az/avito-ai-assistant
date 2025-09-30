from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.routes import chat
from app.services.logs import logger
from contextlib import asynccontextmanager
import asyncio
from app.services.telegram_bot import start_bot


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Фоновый запуск бота при старте FastAPI и инициализация ассистента"""
    bot_task = asyncio.create_task(start_bot())  # Запускаем бота в фоне
    logger.info("FastAPI приложение запущено!")
    yield  # Ждем завершения приложения
    bot_task.cancel()  # Завершаем бота при выключении FastAPI


app = FastAPI(lifespan=lifespan)
class LogRequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        body = await request.body()  # Асинхронное получение тела запроса
        logger.info(f"New request: {request.method} {request.url}")
        logger.info(f"Request body: {body.decode('utf-8')}")

        response = await call_next(request)  # Асинхронный вызов следующего обработчика
        logger.info(f"Response: {response.status_code} {request.url}")
        return response


from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.services.logs import logger


# ... ваш существующий код ...

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Глобальный обработчик ошибок валидации"""
    logger.error(f"❌ Validation error for {request.url}")
    logger.error(f"Errors: {exc.errors()}")
    logger.error(f"Body: {exc.body}")

    return JSONResponse(
        status_code=200,  # Возвращаем 200, чтобы Авито не слал повторно
        content={
            "ok": False,
            "error": "validation_failed",
            "details": exc.errors()
        }
    )

# Добавление middleware в приложение
app.add_middleware(LogRequestMiddleware)

# Подключаем маршруты
app.include_router(chat.router, tags=["Chat"])


@app.get("/")
async def read_root():
    return {
        "message": "AI Assistant is running!"}  # Эта функция уже асинхронная, так как FastAPI её по умолчанию обрабатывает асинхронно
