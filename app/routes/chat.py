from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from app.models.schemas import WebhookRequest
from app.services.avito_api import send_message, get_ad
from app.services.gpt import process_message
import re
from app.services.telegram_bot import send_alert
from app.redis_db import add_chat, chat_exists
router = APIRouter()

# Вынесение джобы в отдельную функцию, чтобы работало как надо
def process_and_send_response(message: WebhookRequest):
    print('1. Генерация ответа на сообщение пользователя')
    response = process_message(message.payload.value.author_id, message.payload.value.content.text)
    print(response)
    print('2. Отправка сгенерированного сообщения')
    send_message(message.payload.value.user_id, message.payload.value.chat_id, response)
    # print("3. Получение информации об объявлении, объявление должно принадлежать владельцу")
    # ad_url = get_ad(message.payload.value.user_id, message.payload.value.item_id)
    print("4. Отправка уведомления в телеграм, если есть слово менеджер или оператор")
    if (re.search('оператор', message.payload.value.content.text, re.IGNORECASE) or
            re.search('менеджер', message.payload.value.content.text, re.IGNORECASE)):
        print("4.1. Перевод сообщения на оператора!")
        # Отправка объявления в чат
        send_alert(f"4.2. Требуется внимание менеджера:\n ссылка")
        # Отключение бота в случае, если по чату была отправлена ссылка
        print("4.3. Добавление чата в список исключений")
        add_chat(message.payload.value.chat_id)

@router.post("/chat")
def chat(message: WebhookRequest, background_tasks: BackgroundTasks):
    print('ПОЛУЧЕН НОВЫЙ ЗАПРОС ОТ АВИТО')

    if message.payload.value.author_id == int(75107414):
        print('0. Вебхук на сообщение от самого себя')
        return JSONResponse(content={"ok": True}, status_code=200)

    if chat_exists(message.payload.value.chat_id):
        print('0. Ассистент отключен в чате')
        return JSONResponse(content={"ok": True}, status_code=200)

    # Добавляем выполнение кода в фоне
    background_tasks.add_task(process_and_send_response, message)

    return JSONResponse(content={"ok": True}, status_code=200)