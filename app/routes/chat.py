from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from app.models.schemas import WebhookRequest
from app.services.avito_api import send_message, get_ad, get_user_info
from app.services.gpt import process_message
import re
from app.services.telegram_bot import send_alert
from app.redis_db import add_chat, chat_exists
import logging
from app.services.logs import send_log

# Используем уже существующий логгер
logger = logging.getLogger("uvicorn")

router = APIRouter()

# Вынесение джобы в отдельную функцию, чтобы работало как надо
def process_and_send_response(message: WebhookRequest):
    send_log(message=f"1. Получение информации о пользователе {message.payload.value.user_id}")
    user_name, user_url = get_user_info(message.payload.value.user_id, message.payload.value.chat_id)
    send_log(message=f"2. Получение информации об объявлении {message.payload.value.item_id}")
    ad_url = get_ad(message.payload.value.user_id, message.payload.value.item_id)
    send_log(message=f"3. Генерация ответа на сообщение пользователя")
    response = process_message(message.payload.value.author_id, message.payload.value.chat_id,
                               message.payload.value.content.text, ad_url)
    if response:
        send_log(f"4. Отправка сгенерированного сообщения", response)

        send_message(message.payload.value.user_id, message.payload.value.chat_id, response)
        send_log(message="5. Отправка сообщения в телеграм канал")
        send_alert(f"💁‍♂️ {user_name}: {message.payload.value.content.text}\n"
                   f"🤖 Бот: {response}\n"
                   f"_____\n\n"
                   f"💬 Диалог: https://www.avito.ru/profile/messenger/channel/{message.payload.value.chat_id}")
        # 5. Отправка уведомления в телеграм, если есть слово менеджер или оператор
        if (re.search('оператор', message.payload.value.content.text, re.IGNORECASE) or
                re.search('менеджер', message.payload.value.content.text, re.IGNORECASE)):
            send_log(message="5.1. Перевод сообщения на оператора!")
            send_alert(f"‼️Требуется внимание менеджера:\n"
                       f"Объявление: {ad_url}\n"
                       f"Клиент {user_name}: {user_url}\n"
                       f"_____\n\n"
                       f"💬Диалог: https://www.avito.ru/profile/messenger/channel/{message.payload.value.chat_id}")
            send_log(message="5.2. Добавление чата в список исключений")
            # Добавление чата в список чатов с выключенным ассистентом
            add_chat(message.payload.value.chat_id)
    else:
        return None

@router.post("/chat")
def chat(message: WebhookRequest, background_tasks: BackgroundTasks):
    send_log(message="ПОЛУЧЕН НОВЫЙ ЗАПРОС ОТ АВИТО")
    message_text = message.payload.value.content.text
    chat_id = message.payload.value.chat_id
    # Проверка наличия чата в списке чатов с выключенным ассистентом
    if chat_exists(chat_id):
        send_log(message="0. Ассистент отключен в чате")

        return JSONResponse(content={"ok": True}, status_code=200)
    # Проверка является ли сообщение сообщением от меня самого
    if message.payload.value.author_id == message.payload.value.user_id:
        if (re.search('оператор', message_text, re.IGNORECASE) or
                re.search('менеджер', message_text, re.IGNORECASE)):
            send_log(message="4.3. Переключение на оператора самим оператором или чат-ботом")

            ad_url = get_ad(message.payload.value.user_id, message.payload.value.item_id)
            user_name, user_url = get_user_info(message.payload.value.user_id, message.payload.value.chat_id)
            send_alert(f"‼️Требуется внимание менеджера:\n"
                       f"Объявление: {ad_url}\n"
                       f"Клиент {user_name}: {user_url}\n"
                       f"_____\n\n"
                       f"💬 Диалог: https://www.avito.ru/profile/messenger/channel/{message.payload.value.chat_id}")
            send_log(message="4.4. Добавление чата в список исключений")

            add_chat(chat_id)
        else:
            send_log(message="0. Вебхук на сообщение от самого себя")

        return JSONResponse(content={"ok": True}, status_code=200)

    # Добавляем выполнение кода в фоне
    background_tasks.add_task(process_and_send_response, message)

    return JSONResponse(content={"ok": True}, status_code=200)