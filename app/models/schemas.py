from pydantic import BaseModel
from typing import Optional

# Модели для обработки данных
class MessageContent(BaseModel):
    text: Optional[str] = None

class Value(BaseModel):
    id: str
    chat_id: str
    user_id: int
    author_id: int
    created: int
    type: str
    chat_type: str
    content: MessageContent
    item_id: Optional[int] = None
    published_at: str

class Payload(BaseModel):
    type: str
    value: Value

class WebhookRequest(BaseModel):
    id: str
    version: str
    timestamp: int
    payload: Payload