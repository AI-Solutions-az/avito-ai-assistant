from fastapi import APIRouter
from app.models.schemas import Value
from app.services.gpt import process_message

router = APIRouter()

@router.post("/chat/")
async def chat(message: Value):
    response = process_message(message.author_id, message.content.text)
    return {"response": response}