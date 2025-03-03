from fastapi import APIRouter
from app.models.schemas import WebhookRequest
from app.services.avito_api import send_message
from app.services.gpt import process_message
from fastapi.responses import JSONResponse

router = APIRouter()

@router.post("/chat")
def chat(message: WebhookRequest):
    print('ПОЛУЧЕН НОВЫЙ ЗАПРОС ОТ АВИТО')
    if message.payload.value.author_id ==int(75107414):
        print('0. Вебхук на сообщение от самого себя')
        return JSONResponse(content={"ok":True}, status_code=200)
    print('1. Генерация ответа на сообщение пользователя')
    response = process_message(message.payload.value.author_id, message.payload.value.content.text)
    # print('2. Отправка сгенерированного сообщения')
    # send_message(message.payload.value.user_id, message.payload.value.chat_id, response)
    return JSONResponse(content={"ok":True}, status_code=200)
