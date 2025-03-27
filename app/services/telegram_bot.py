import logging
import requests
import os
from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
# Настройка логирования
logger = logging.getLogger("uvicorn")


# Отправка сообщения в чат
def send_alert(message, thread_id):
    logger.info(f"Отправка уведомления в Telegram: {message}")

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "message_thread_id":thread_id, "text": message}

    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        logger.info("Уведомление успешно отправлено в Telegram")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при отправке уведомления в Telegram: {e}")
        raise


def create_telegram_forum_topic(topic_name):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/createForumTopic'

    # Параметры для создания топика
    params = {
        'chat_id': TELEGRAM_CHAT_ID,
        'name': topic_name,
        'title': '12345'
    }

    # Отправка запроса
    response = requests.post(url, data=params)

    # Проверка ответа
    if response.status_code == 200:
        print(f"Топик '{topic_name}' успешно создан!")
    else:
        print(f"Ошибка при создании топика: {response.text}")
