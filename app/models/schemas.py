from pydantic import BaseModel

# Модели для обработки данных
class MessageContent(BaseModel):
    text: str = None

class Message(BaseModel):
    author_id: int
    chat_id: str
    chat_type: str
    content: MessageContent
    id: str
    item_id: int = None
    type: str