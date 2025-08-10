import os
import time
from pathlib import Path
from typing import Optional, Tuple
from openai import OpenAI

from app.config import settings, OPENAI_API_KEY
from app.services.logs import logger
from app.models.voice_schemas import VoiceError, VoiceErrorCodes, VoiceProcessingResult, VoiceProcessingStatus
from app.services.audio_downloader import audio_downloader

# Проверяем наличие mutagen для анализа аудио метаданных
try:
    from mutagen import File as MutagenFile

    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    logger.warning("[VoiceRecognition] Mutagen не установлен, анализ метаданных недоступен")


class VoiceRecognition:
    """Класс для распознавания речи через OpenAI Whisper API"""

    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = settings.WHISPER_MODEL
        self.max_duration = settings.MAX_AUDIO_DURATION
        logger.info(f"[VoiceRecognition] Инициализирован с моделью: {self.model}")

    async def transcribe_audio(self, file_path: str, chat_id: str, message_id: str) -> Tuple[
        Optional[str], Optional[VoiceError]]:
        """
        Распознает речь из аудио файла

        Args:
            file_path: Путь к аудио файлу
            chat_id: ID чата для логирования
            message_id: ID сообщения для логирования

        Returns:
            Tuple[transcribed_text, error]: Распознанный текст или ошибка
        """
        start_time = time.time()
        logger.info(f"[VoiceRecognition] Начинаем распознавание для чата {chat_id}, сообщение {message_id}")

        try:
            # Проверяем существование файла
            if not os.path.exists(file_path):
                error = VoiceError(
                    code=VoiceErrorCodes.DOWNLOAD_FAILED,
                    message=f"Аудио файл не найден: {file_path}"
                )
                return None, error

            # Проверяем размер файла
            file_size = os.path.getsize(file_path)
            max_size_bytes = settings.MAX_AUDIO_SIZE_MB * 1024 * 1024
            if file_size > max_size_bytes:
                size_mb = file_size / (1024 * 1024)
                error = VoiceError(
                    code=VoiceErrorCodes.FILE_TOO_LARGE,
                    message=f"Файл слишком большой: {size_mb:.1f} МБ"
                )
                return None, error

            # Анализируем метаданные аудио (если доступно)
            audio_info = await self._analyze_audio_metadata(file_path)
            if audio_info and audio_info.get("duration"):
                duration = audio_info["duration"]
                if duration > self.max_duration:
                    minutes = duration / 60
                    max_minutes = self.max_duration / 60
                    error = VoiceError(
                        code=VoiceErrorCodes.DURATION_TOO_LONG,
                        message=f"Длительность аудио {minutes:.1f} мин превышает лимит {max_minutes:.1f} мин"
                    )
                    return None, error
                logger.info(f"[VoiceRecognition] Длительность аудио: {duration:.1f}с")

            # Отправляем в Whisper API
            logger.info(f"[VoiceRecognition] Отправляем файл в Whisper API: {file_path}")

            with open(file_path, "rb") as audio_file:
                try:
                    response = self.client.audio.transcriptions.create(
                        model=self.model,
                        file=audio_file,
                        language="ru",  # Указываем русский язык для лучшего качества
                        response_format="text",
                        temperature=0.0  # Минимальная температура для более точного распознавания
                    )

                    # Whisper возвращает строку при response_format="text"
                    transcribed_text = response.strip() if isinstance(response, str) else str(response).strip()

                    if not transcribed_text:
                        logger.warning(f"[VoiceRecognition] Whisper вернул пустой результат для {message_id}")
                        error = VoiceError(
                            code=VoiceErrorCodes.TRANSCRIPTION_FAILED,
                            message="Не удалось распознать речь в аудио сообщении"
                        )
                        return None, error

                    processing_time = time.time() - start_time
                    logger.info(
                        f"[VoiceRecognition] Успешно распознано за {processing_time:.2f}с: '{transcribed_text[:50]}...'")

                    return transcribed_text, None

                except Exception as whisper_error:
                    logger.error(f"[VoiceRecognition] Ошибка Whisper API: {whisper_error}")

                    # Анализируем тип ошибки от OpenAI
                    error_message = str(whisper_error)
                    if "file size" in error_message.lower():
                        error = VoiceError(
                            code=VoiceErrorCodes.FILE_TOO_LARGE,
                            message="Файл слишком большой для Whisper API"
                        )
                    elif "duration" in error_message.lower():
                        error = VoiceError(
                            code=VoiceErrorCodes.DURATION_TOO_LONG,
                            message="Аудио слишком длинное для обработки"
                        )
                    elif "format" in error_message.lower():
                        error = VoiceError(
                            code=VoiceErrorCodes.UNSUPPORTED_FORMAT,
                            message="Неподдерживаемый формат аудио файла"
                        )
                    else:
                        error = VoiceError(
                            code=VoiceErrorCodes.TRANSCRIPTION_FAILED,
                            message=f"Ошибка распознавания речи: {error_message}"
                        )

                    return None, error

        except FileNotFoundError:
            logger.error(f"[VoiceRecognition] Файл не найден: {file_path}")
            error = VoiceError(
                code=VoiceErrorCodes.DOWNLOAD_FAILED,
                message="Аудио файл не найден"
            )
            return None, error

        except PermissionError:
            logger.error(f"[VoiceRecognition] Нет доступа к файлу: {file_path}")
            error = VoiceError(
                code=VoiceErrorCodes.DOWNLOAD_FAILED,
                message="Нет доступа к аудио файлу"
            )
            return None, error

        except Exception as e:
            logger.error(f"[VoiceRecognition] Неожиданная ошибка при распознавании: {e}")
            error = VoiceError(
                code=VoiceErrorCodes.TRANSCRIPTION_FAILED,
                message=f"Неожиданная ошибка: {str(e)}"
            )
            return None, error

    async def _analyze_audio_metadata(self, file_path: str) -> Optional[dict]:
        """Анализирует метаданные аудио файла"""
        if not MUTAGEN_AVAILABLE:
            return None

        try:
            audio_file = MutagenFile(file_path)
            if audio_file is None:
                logger.warning(f"[VoiceRecognition] Не удалось проанализировать метаданные: {file_path}")
                return None

            info = {
                "duration": getattr(audio_file.info, 'length', None),
                "bitrate": getattr(audio_file.info, 'bitrate', None),
                "channels": getattr(audio_file.info, 'channels', None),
                "sample_rate": getattr(audio_file.info, 'sample_rate', None)
            }

            logger.info(f"[VoiceRecognition] Метаданные аудио: {info}")
            return info

        except Exception as e:
            logger.warning(f"[VoiceRecognition] Ошибка анализа метаданных: {e}")
            return None

   async def process_voice_message(self, voice_url: str, chat_id: str, message_id: str, user_id: int) -> VoiceProcessingResult:
        """
        Полный цикл обработки голосового сообщения

        Args:
            voice_url: voice_id голосового сообщения от Avito
            chat_id: ID чата
            message_id: ID сообщения
            user_id: ID пользователя (для API запроса)

        Returns:
            VoiceProcessingResult: Результат обработки с текстом или ошибкой
        """
        start_time = time.time()
        logger.info(f"[VoiceRecognition] Начинаем полную обработку голосового сообщения {message_id} в чате {chat_id}")

        result = VoiceProcessingResult(
            chat_id=chat_id,
            message_id=message_id,
            status=VoiceProcessingStatus.PENDING
        )

        try:
            # Этап 1: Скачивание
            result.status = VoiceProcessingStatus.DOWNLOADING
            logger.info(f"[VoiceRecognition] Этап 1: Скачивание аудио файла")

            # voice_url здесь на самом деле voice_id
            voice_id = voice_url
            file_path, download_error = await audio_downloader.download_voice_file(
                voice_id, chat_id, message_id, user_id
            )

            if download_error or not file_path:
                result.status = VoiceProcessingStatus.FAILED
                result.error_message = download_error.message if download_error else "Неизвестная ошибка скачивания"
                return result

            try:
                # Сохраняем информацию о файле
                file_size = os.path.getsize(file_path)
                result.file_size = file_size

                # Анализируем метаданные
                audio_info = await self._analyze_audio_metadata(file_path)
                if audio_info:
                    result.audio_duration = audio_info.get("duration")

                # Этап 2: Распознавание
                result.status = VoiceProcessingStatus.TRANSCRIBING
                logger.info(f"[VoiceRecognition] Этап 2: Распознавание речи")

                transcribed_text, transcription_error = await self.transcribe_audio(
                    file_path, chat_id, message_id
                )

                if transcription_error or not transcribed_text:
                    result.status = VoiceProcessingStatus.FAILED
                    result.error_message = transcription_error.message if transcription_error else "Не удалось распознать речь"
                    return result

                # Успешное завершение
                result.status = VoiceProcessingStatus.COMPLETED
                result.transcribed_text = transcribed_text
                result.processing_time = time.time() - start_time

                logger.info(f"[VoiceRecognition] ✅ Обработка завершена успешно за {result.processing_time:.2f}с")
                logger.info(f"[VoiceRecognition] Распознанный текст: '{transcribed_text[:100]}...'")

                return result

            finally:
                # Всегда удаляем временный файл
                if file_path:
                    await audio_downloader.cleanup_file(file_path)

        except Exception as e:
            logger.error(f"[VoiceRecognition] Критическая ошибка при обработке: {e}")
            result.status = VoiceProcessingStatus.FAILED
            result.error_message = f"Критическая ошибка: {str(e)}"
            result.processing_time = time.time() - start_time
            return result

    def is_voice_recognition_enabled(self) -> bool:
        """Проверяет включен ли модуль распознавания голоса"""
        return settings.VOICE_RECOGNITION_ENABLED

    async def get_processing_stats(self) -> dict:
        """Возвращает статистику обработки (для мониторинга)"""
        temp_dir = Path(settings.AUDIO_TEMP_DIR)
        temp_files_count = len(list(temp_dir.glob("*"))) if temp_dir.exists() else 0

        return {
            "voice_recognition_enabled": self.is_voice_recognition_enabled(),
            "whisper_model": self.model,
            "max_file_size_mb": settings.MAX_AUDIO_SIZE_MB,
            "max_duration_seconds": self.max_duration,
            "temp_files_count": temp_files_count,
            "temp_directory": str(temp_dir),
            "mutagen_available": MUTAGEN_AVAILABLE
        }


# Создаем глобальный экземпляр
voice_recognition = VoiceRecognition()
