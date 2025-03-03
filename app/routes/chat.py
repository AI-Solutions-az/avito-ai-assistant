from fastapi import APIRouter, BackgroundTasks
from app.models.schemas import WebhookRequest
from app.services.avito_api import send_message
from app.services.gpt import process_message
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/chat")
async def chat(message: WebhookRequest, background_tasks: BackgroundTasks):
    # Автор последнего сообщения
    if message.payload.value.author_id == int(75107414):
        return None
    else:
        # Генерация ответа на сообщение пользователя
        response = process_message(message.payload.value.author_id, message.payload.value.content.text)

        # Добавляем задачу на выполнение в фоне
        background_tasks.add_task(send_message, message.payload.value.user_id, message.payload.value.chat_id,
                                  response)

        # Возвращаем ответ с кодом 200
        return JSONResponse(content={"response": response}, status_code=200)
