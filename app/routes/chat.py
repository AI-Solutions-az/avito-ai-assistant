import time

from fastapi import APIRouter
from app.models.schemas import WebhookRequest
from app.services.avito_api import send_message
from app.services.gpt import process_message

router = APIRouter()

@router.post("/chat")
async def chat(message: WebhookRequest):
    # Автор последнего сообщения
    time.sleep(5)
    if message.payload.value.author_id ==int(75107414):
        return None
    else:
        # Генерация ответа на сообщение пользователя
        response = process_message(message.payload.value.author_id, message.payload.value.content.text)
        time.sleep(5)
        # Отправка сгенерированного сообщения
        send_message(message.payload.value.user_id, message.payload.value.chat_id, response)
        return None # {"response": response}
