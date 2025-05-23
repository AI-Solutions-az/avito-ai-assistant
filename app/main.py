# app/main.py - Updated version

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.routes import chat
from app.routes import client_management  # NEW: Add client management routes
from app.services.logs import logger
from contextlib import asynccontextmanager
import asyncio
from app.services.telegram_bot import start_bot
from app.services.client_telegram_notifier import cleanup_client_bots  # NEW: Cleanup function


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Background bot startup and cleanup"""
    bot_task = asyncio.create_task(start_bot())
    logger.info("FastAPI application started!")
    yield  # Wait for application shutdown

    # NEW: Cleanup client bot sessions
    await cleanup_client_bots()
    bot_task.cancel()
    logger.info("FastAPI application shutdown complete!")


app = FastAPI(lifespan=lifespan)


class LogRequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        body = await request.body()
        logger.info(f"New request: {request.method} {request.url}")
        logger.info(f"Request body: {body.decode('utf-8')}")

        response = await call_next(request)
        logger.info(f"Response: {response.status_code} {request.url}")
        return response


# Add middleware
app.add_middleware(LogRequestMiddleware)

# Connect routes
app.include_router(chat.router, tags=["Chat"])
app.include_router(client_management.router, prefix="/api", tags=["Client Management"])  # NEW: Client management API


@app.get("/")
async def read_root():
    return {"message": "AI Assistant with Multi-Client Support is running!"}