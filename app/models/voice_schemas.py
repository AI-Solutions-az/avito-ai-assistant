from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

# 🎙️ СПЕЦИАЛИЗИРОВАННЫЕ СХЕМЫ ТОЛЬКО ДЛЯ ГОЛОСОВОГО МОДУЛЯ
# (НЕ дублируем WebhookRequest - он в schemas.py)

class VoiceProcessingStatus(str, Enum):
    """Статус обработки голосового сообщения"""
    PENDING = "pending"          # Ожидает обработки
    DOWNLOADING = "downloading"   # Скачивается
    TRANSCRIBING = "transcribing" # Распознается
    COMPLETED = "completed"      # Завершено
    FAILED = "failed"           # Ошибка

class AudioFormat(str, Enum):
    """Поддерживаемые форматы аудио"""
    MP3 = "mp3"
    OGG = "ogg"
    WAV = "wav"
    M4A = "m4a"
    WEBM = "webm"

class VoiceProcessingResult(BaseModel):
    """Результат обработки голосового сообщения"""
    chat_id: str
    message_id: str
    status: VoiceProcessingStatus
    transcribed_text: Optional[str] = None
    error_message: Optional[str] = None
    processing_time: Optional[float] = None
    audio_duration: Optional[float] = None
    file_size: Optional[int] = None
    audio_format: Optional[AudioFormat] = None

class VoiceSettings(BaseModel):
    """Настройки голосового модуля"""
    enabled: bool = True
    whisper_model: str = "whisper-1"
    max_file_size_mb: int = 25
    max_duration_seconds: int = 300
    download_timeout_seconds: int = 30
    supported_formats: list[AudioFormat] = [
        AudioFormat.MP3,
        AudioFormat.OGG,
        AudioFormat.WAV,
        AudioFormat.M4A,
        AudioFormat.WEBM
    ]

class VoiceError(BaseModel):
    """Ошибка обработки голосового сообщения"""
    code: str
    message: str
    details: Optional[dict] = None

# Константы для ошибок
class VoiceErrorCodes:
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    DURATION_TOO_LONG = "DURATION_TOO_LONG"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    TRANSCRIPTION_FAILED = "TRANSCRIPTION_FAILED"
    NETWORK_ERROR = "NETWORK_ERROR"
    INVALID_URL = "INVALID_URL"
    PROCESSING_TIMEOUT = "PROCESSING_TIMEOUT"