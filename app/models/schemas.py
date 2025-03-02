from pydantic import BaseModel
from typing import Optional

# Модель для содержимого сообщения (content)
class MessageContent(BaseModel):
    text: str

# Модель для значения сообщения (value)
class MessageValue(BaseModel):
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

# Модель для полезной нагрузки (payload)
class Payload(BaseModel):
    type: str
    value: MessageValue

# Основная модель для всего запроса
class WebhookRequest(BaseModel):
    id: str
    version: str
    timestamp: int
    payload: Payload