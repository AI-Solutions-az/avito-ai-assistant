from fastapi import APIRouter
from app.models.schemas import WebhookRequest
from app.services.gpt import process_message

router = APIRouter()

@router.post("/chat/")
async def chat(message: WebhookRequest):
    response = process_message(message.payload.value.author_id, message.payload.value.content.text)
    return {"response": response}