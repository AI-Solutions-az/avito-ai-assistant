import logging
import httpx
import os

# Настройка логирования
logger = logging.getLogger("uvicorn")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


async def send_alert(message):
    logger.info(f"Отправка уведомления в Telegram: {message}")

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, data=data)
            response.raise_for_status()
            logger.info("Уведомление успешно отправлено в Telegram")
        except httpx.RequestError as e:
            logger.error(f"Ошибка при отправке уведомления в Telegram: {e}")
            raise