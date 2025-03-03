import time

from fastapi import APIRouter
from app.models.schemas import WebhookRequest
from app.services.avito_api import send_message
from app.services.gpt import process_message

router = APIRouter()

@router.post("/chat")
async def chat(message: WebhookRequest):
    # Автор последнего сообщения
    print("Автор последнего сообщения:", message.payload.value.author_id)
    # Генерация ответа на сообщение пользователя
    if message.payload.value.author_id !=75107414:
        response = process_message(message.payload.value.author_id, message.payload.value.content.text)
        # Отправка сгенерированного сообщения
        send_message(message.payload.value.user_id, message.payload.value.chat_id, response)
        return {"response": response}
    else:
        return None