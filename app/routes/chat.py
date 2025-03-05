from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from app.models.schemas import WebhookRequest
from app.services.avito_api import send_message, get_ad
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
    logger.info('1. Генерация ответа на сообщение пользователя')
    response = process_message(message.payload.value.author_id, message.payload.value.content.text)
    logger.info(f"Ответ: {response}")
    logger.info('2. Отправка сгенерированного сообщения')
    send_message(message.payload.value.user_id, message.payload.value.chat_id, response)
    # print("3. Получение информации об объявлении, объявление должно принадлежать владельцу")
    # ad_url = get_ad(message.payload.value.user_id, message.payload.value.item_id)
    logger.info("4. Отправка уведомления в телеграм, если есть слово менеджер или оператор")
    if (re.search('оператор', message.payload.value.content.text, re.IGNORECASE) or
            re.search('менеджер', message.payload.value.content.text, re.IGNORECASE)):
        logger.info("4.1. Перевод сообщения на оператора!")
        send_alert(f"Требуется внимание менеджера:\n ссылка")

        logger.info("4.2. Добавление чата в список исключений")
        add_chat(message.payload.value.chat_id)

@router.post("/chat")
def chat(message: WebhookRequest, background_tasks: BackgroundTasks):
    logger.info('ПОЛУЧЕН НОВЫЙ ЗАПРОС ОТ АВИТО')
    print(message)
    author_id = int(75107414)
    message_text = message.payload.value.content.text
    chat_id = message.payload.value.chat_id

    if chat_exists(chat_id):
        logger.info('0. Ассистент отключен в чате')
        return JSONResponse(content={"ok": True}, status_code=200)

    if message.payload.value.author_id == author_id:
        if (re.search('оператор', message_text, re.IGNORECASE) or
                re.search('менеджер', message_text, re.IGNORECASE)):
            logger.info("4.3. Переключение на оператора самим оператором или чат-ботом")
            send_alert(f"Требуется внимание менеджера:\n ссылка")
            logger.info("4.4. Добавление чата в список исключений")
            add_chat(chat_id)
        else:
            logger.info('0. Вебхук на сообщение от самого себя')
        return JSONResponse(content={"ok": True}, status_code=200)

    # Добавляем выполнение кода в фоне
    background_tasks.add_task(process_and_send_response, message)

    return JSONResponse(content={"ok": True}, status_code=200)