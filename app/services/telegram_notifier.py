from aiogram.types import Message, ForumTopicCreated
from app.services.logs import logger
from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from app.services.telegram_bot import bot

# ✅ Отправка сообщения в чат
async def send_alert(message: str, thread_id: int):
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, message_thread_id=thread_id)
        logger.info("✅ Уведомление успешно отправлено в Telegram")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомления в Telegram: {e}")
        raise


# ✅ Создание форума (топика)
async def create_telegram_forum_topic(topic_name: str):
    try:
        response = await bot.create_forum_topic(chat_id=TELEGRAM_CHAT_ID, name=topic_name)
        if isinstance(response, ForumTopicCreated):
            logger.info(f"✅ Топик '{topic_name}' успешно создан!")
            return response.message_thread_id  # Возвращаем thread_id созданного топика
    except Exception as e:
        logger.error(f"❌ Ошибка при создании топика: {e}")
        raise


# ✅ Получение последнего thread_id
async def get_telegram_updates():
    try:
        updates = await bot.get_updates()
        for update in updates:
            if update.message and update.message.message_thread_id:
                return update.message.message_thread_id
        logger.info("Не найден thread_id в сообщении.")
    except Exception as e:
        logger.error(f"❌ Ошибка при получении обновлений: {e}")