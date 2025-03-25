from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from app.models.schemas import WebhookRequest
from app.services.avito_api import send_message, get_ad, get_user_info
from app.services.gpt import process_message
import re
from app.services.telegram_bot import send_alert
from app.redis_db import add_chat, chat_exists
import logging

# Используем уже существующий логгер
logger = logging.getLogger("uvicorn")

router = APIRouter()

# Вынесение джобы в отдельную функцию, чтобы работало как надо
def process_and_send_response(message: WebhookRequest):
    logger.info("1. Получение информации о пользователе")
    user_name, user_url = get_user_info(message.payload.value.user_id, message.payload.value.chat_id)
    logger.info("2. Получение информации об объявлении, объявление должно принадлежать владельцу")
    ad_url = get_ad(message.payload.value.user_id, message.payload.value.item_id)
    logger.info('3. Генерация ответа на сообщение пользователя')
    response = process_message(message.payload.value.author_id, message.payload.value.chat_id,
                               message.payload.value.content.text, ad_url)
    if response:
        logger.info(f"Ответ: {response}")
        logger.info('4. Отправка сгенерированного сообщения')
        send_message(message.payload.value.user_id, message.payload.value.chat_id, response)
        logger.info("5. Отправка сообщения в телеграм канал")
        send_alert(f"💁‍♂️ {user_name}: {message.payload.value.content.text}\n"
                   f"🤖 Бот: {response}"
                   f"Диалог: https://www.avito.ru/profile/messenger/channel/{message.payload.value.chat_id}")
        # 5. Отправка уведомления в телеграм, если есть слово менеджер или оператор
        if (re.search('оператор', message.payload.value.content.text, re.IGNORECASE) or
                re.search('менеджер', message.payload.value.content.text, re.IGNORECASE)):
            logger.info("5.1. Перевод сообщения на оператора!")
            send_alert(f"Требуется внимание менеджера:\n"
                       f"Объявление: {ad_url}\n"
                       f"Клиент {user_name}: {user_url}"
                       f"Диалог: https://www.avito.ru/profile/messenger/channel/{message.payload.value.chat_id}")
            logger.info("5.2. Добавление чата в список исключений")
            add_chat(message.payload.value.chat_id)
    else:
        return None

@router.post("/chat")
def chat(message: WebhookRequest, background_tasks: BackgroundTasks):
    logger.info('ПОЛУЧЕН НОВЫЙ ЗАПРОС ОТ АВИТО')
    logger.info(message)
    message_text = message.payload.value.content.text
    chat_id = message.payload.value.chat_id

    if chat_exists(chat_id):
        logger.info('0. Ассистент отключен в чате')
        return JSONResponse(content={"ok": True}, status_code=200)

    if message.payload.value.author_id == message.payload.value.user_id:
        if (re.search('оператор', message_text, re.IGNORECASE) or
                re.search('менеджер', message_text, re.IGNORECASE)):
            logger.info("4.3. Переключение на оператора самим оператором или чат-ботом")
            ad_url = get_ad(message.payload.value.user_id, message.payload.value.item_id)
            user_name, user_url = get_user_info(message.payload.value.user_id, message.payload.value.chat_id)
            send_alert(f"Требуется внимание менеджера:\n"
                       f"Объявление: {ad_url}\n"
                       f"Клиент {user_name}: {user_url}"
                       f"Диалог: https://www.avito.ru/profile/messenger/channel/{message.payload.value.chat_id}")
            logger.info("4.4. Добавление чата в список исключений")
            add_chat(chat_id)
        else:
            logger.info('0. Вебхук на сообщение от самого себя')
        return JSONResponse(content={"ok": True}, status_code=200)

    # Добавляем выполнение кода в фоне
    background_tasks.add_task(process_and_send_response, message)

    return JSONResponse(content={"ok": True}, status_code=200)