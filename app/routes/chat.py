from fastapi import APIRouter
from app.models.schemas import WebhookRequest
from app.services.avito_api import send_message
from app.services.gpt import process_message

router = APIRouter()

@router.post("/chat/")
async def chat(message: WebhookRequest):
    response = process_message(message.payload.value.author_id, message.payload.value.content.text)
    send_message(message.payload.value.user_id, message.payload.value.chat_id, response)
    return {"response": response}