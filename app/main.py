from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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

# УБИРАЕМ MIDDLEWARE ПОЛНОСТЬЮ - он мешал чтению body

# ОБРАБОТЧИК ОШИБОК ВАЛИДАЦИИ
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Обработчик ошибок валидации Pydantic"""
    logger.error(f"=== VALIDATION ERROR ===")
    logger.error(f"URL: {request.method} {request.url}")
    logger.error(f"Validation errors count: {len(exc.errors())}")
    
    for i, error in enumerate(exc.errors()):
        logger.error(f"Error {i+1}:")
        logger.error(f"  Location: {error['loc']}")
        logger.error(f"  Message: {error['msg']}")
        logger.error(f"  Type: {error['type']}")
    
    logger.error(f"=== END VALIDATION ERROR ===")
    
    return JSONResponse(
        status_code=400,
        content={
            "detail": "Validation error",
            "errors": exc.errors()
        }
    )


# Подключаем маршруты
app.include_router(chat.router, tags=["Chat"])


@app.get("/")
async def read_root():
    return {"message": "AI Assistant is running!"}


@app.get("/status") 
async def status():
    return {"status": "running", "message": "Server is working"}
