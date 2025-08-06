from pydantic import BaseModel, field_validator
from typing import Optional, Any


# 🎙️ ОБНОВЛЕННЫЕ МОДЕЛИ С ПОДДЕРЖКОЙ ГОЛОСОВЫХ СООБЩЕНИЙ

# Универсальная модель содержимого (текст или голос)
class MessageContent(BaseModel):
    # Для текстовых сообщений
    text: Optional[str] = None

    # Для голосовых сообщений
    url: Optional[str] = None
    duration: Optional[int] = None
    size: Optional[int] = None
    format: Optional[str] = None

    @field_validator('text', 'url', 'format', mode='before')
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Any:
        """Преобразует пустые строки в None"""
        if v == '':
            return None
        return v


# Модель для значения сообщения (value)
class MessageValue(BaseModel):
    id: str
    chat_id: str
    user_id: int
    author_id: int
    created: int
    type: str  # "text" или "voice"
    chat_type: str
    content: MessageContent  # Универсальное содержимое
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

    def is_voice_message(self) -> bool:
        """Проверяет является ли сообщение голосовым"""
        return (
                self.payload.value.type == "voice" and
                self.payload.value.content.url is not None and
                self.payload.value.content.url.strip() != ""
        )

    def is_text_message(self) -> bool:
        """Проверяет является ли сообщение текстовым"""
        return (
                self.payload.value.type == "text" and
                self.payload.value.content.text is not None and
                self.payload.value.content.text.strip() != ""
        )

    def get_message_text(self) -> Optional[str]:
        """Возвращает текст сообщения (для текстовых сообщений)"""
        if self.is_text_message():
            return self.payload.value.content.text
        return None

    def get_voice_url(self) -> Optional[str]:
        """Возвращает URL голосового сообщения"""
        if self.is_voice_message():
            return self.payload.value.content.url
        return None

    def get_voice_duration(self) -> Optional[int]:
        """Возвращает длительность голосового сообщения в секундах"""
        if self.is_voice_message():
            return self.payload.value.content.duration
        return None


# Модель для результата обработки сообщения (для внутреннего использования)
class ProcessedMessage(BaseModel):
    chat_id: str
    message_id: str
    user_id: int
    author_id: int
    message_type: str  # "text" или "voice"
    original_content: str  # Оригинальный текст или URL
    processed_text: str  # Финальный текст для обработки
    is_from_voice: bool = False  # Был ли текст получен из голосового сообщения
    voice_processing_time: Optional[float] = None  # Время обработки голоса в секундах