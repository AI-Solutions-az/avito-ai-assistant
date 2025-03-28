import asyncio

from aiogram.types import ForumTopicCreated
from app.services.logs import logger
from app.config import TELEGRAM_CHAT_ID
from app.services.telegram_bot import bot

# ✅ Отправка сообщения в чат
async def send_alert(message: str, thread_id: int):
    logger.info(f"Отправка уведомления в телеграм по треду {thread_id}")
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, message_thread_id=thread_id)
        logger.info("✅ Уведомление успешно отправлено в Telegram")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомления в Telegram: {e}")
        raise


# ✅ Создание форума (топика)
async def create_telegram_forum_topic(topic_name: str):
    logger.info(f"[API] Создание топика Telegram {topic_name}")
    try:
        response = await bot.create_forum_topic(chat_id=TELEGRAM_CHAT_ID, name=topic_name)
        return response.message_thread_id  # Возвращаем thread_id созданного топика
    except Exception as e:
        logger.error(f"❌ Ошибка при создании топика: {e}")
        raise