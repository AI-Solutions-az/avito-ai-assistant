from pydantic import BaseModel

# Модели для обработки данных
class MessageContent(BaseModel):
    text: str

class Value(BaseModel):
    id: str
    chat_id: str
    user_id: int
    author_id: int
    created: int
    type: str
    chat_type: str
    content: MessageContent
    item_id: int
    published_at: str

class Payload(BaseModel):
    type: str
    value: Value

class WebhookRequest(BaseModel):
    id: str
    version: str
    timestamp: int
    payload: Payload