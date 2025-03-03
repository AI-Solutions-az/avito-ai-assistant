from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from app.models.schemas import WebhookRequest
from app.services.avito_api import send_message
from app.services.gpt import process_message

router = APIRouter()

def process_and_send_response(message: WebhookRequest):
    print('1. Генерация ответа на сообщение пользователя')
    response = process_message(message.payload.value.author_id, message.payload.value.content.text)
    print(response)
    print('2. Отправка сгенерированного сообщения')
    send_message(message.payload.value.user_id, message.payload.value.chat_id, response)

@router.post("/chat")
def chat(message: WebhookRequest, background_tasks: BackgroundTasks):
    print('ПОЛУЧЕН НОВЫЙ ЗАПРОС ОТ АВИТО')

    if message.payload.value.author_id == int(75107414):
        print('0. Вебхук на сообщение от самого себя')
        return JSONResponse(content={"ok": True}, status_code=200)

    # Добавляем выполнение кода в фоне
    background_tasks.add_task(process_and_send_response, message)

    return JSONResponse(content={"ok": True}, status_code=200)