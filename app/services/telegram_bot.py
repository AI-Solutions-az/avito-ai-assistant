import httpx
from app.services.logs import logger
from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Отправка сообщения в чат
async def send_alert(message, thread_id):
    logger.info(f"Отправка уведомления в Telegram: {message}")

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "message_thread_id": thread_id, "text": message}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, data=data)
            response.raise_for_status()
            logger.info("Уведомление успешно отправлено в Telegram")
        except httpx.RequestError as e:
            logger.error(f"Ошибка при отправке уведомления в Telegram: {e}")
            raise


# Асинхронная функция для создания форума
async def create_telegram_forum_topic(topic_name):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/createForumTopic'

    # Параметры для создания топика
    params = {
        'chat_id': TELEGRAM_CHAT_ID,
        'name': topic_name
    }

    async with httpx.AsyncClient() as client:
        try:
            # Отправка запроса
            response = await client.post(url, data=params)

            # Проверка ответа
            if response.status_code == 200:
                logger.info(f"Топик '{topic_name}' успешно создан!")
            else:
                logger.error(f"Ошибка при создании топика: {response.text}")
        except httpx.RequestError as e:
            logger.error(f"Ошибка при отправке запроса: {e}")