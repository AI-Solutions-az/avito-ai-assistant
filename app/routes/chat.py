from fastapi import APIRouter
from app.models.schemas import WebhookRequest
from app.services.avito_api import send_message
from app.services.gpt import process_message
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/chat")
async def chat(message: WebhookRequest):
    # Автор последнего сообщения
    if message.payload.value.author_id == int(75107414):
        return None
    else:
        # Генерация ответа на сообщение пользователя
        response = process_message(message.payload.value.author_id, message.payload.value.content.text)

        # Возвращаем ответ с кодом 200
        result = {"response": response}

        # Отправка сгенерированного сообщения после формирования ответа
        await send_message(message.payload.value.user_id, message.payload.value.chat_id, response)

        return JSONResponse(content=result, status_code=200)