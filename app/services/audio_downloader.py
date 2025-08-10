import os
import httpx
import aiofiles
from pathlib import Path
from typing import Optional, Tuple
import uuid
from urllib.parse import urlparse

from app.config import settings, CLIENT_ID, CLIENT_SECRET
from app.services.logs import logger
from app.models.voice_schemas import VoiceError, VoiceErrorCodes, AudioFormat
from app.services.avito_api import get_avito_token


class AudioDownloader:
    """Класс для скачивания аудио файлов от Avito"""

    def __init__(self):
        self.temp_dir = Path(settings.AUDIO_TEMP_DIR)
        self.max_size_bytes = settings.MAX_AUDIO_SIZE_MB * 1024 * 1024
        self.timeout = settings.AUDIO_DOWNLOAD_TIMEOUT

        # Создаем временную директорию если не существует
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[AudioDownloader] Временная директория: {self.temp_dir}")

    async def download_voice_file(self, voice_identifier: str, chat_id: str, message_id: str) -> Tuple[
        Optional[str], Optional[VoiceError]]:
        """
        Скачивает голосовой файл по URL или voice_id

        Args:
            voice_identifier: URL аудио файла или voice_id от Avito
            chat_id: ID чата для логирования
            message_id: ID сообщения для уникального имени файла

        Returns:
            Tuple[file_path, error]: Путь к скачанному файлу или ошибка
        """
        logger.info(f"[AudioDownloader] Начинаем скачивание аудио для чата {chat_id}, сообщение {message_id}")

        try:
            # Определяем это URL или voice_id
            if voice_identifier.startswith('http'):
                # Это прямой URL
                voice_url = voice_identifier
            else:
                # Это voice_id, формируем URL для скачивания через Avito API
                voice_url = f"https://api.avito.ru/messenger/v2/accounts/self/chats/{chat_id}/messages/{message_id}/voice"
                logger.info(f"[AudioDownloader] Сформирован URL для voice_id: {voice_url}")

            # Валидация URL
            if not self._is_valid_url(voice_url):
                error = VoiceError(
                    code=VoiceErrorCodes.INVALID_URL,
                    message=f"Некорректный URL: {voice_url}"
                )
                return None, error

            # Генерируем уникальное имя файла
            file_extension = self._extract_file_extension(voice_url)
            filename = f"{chat_id}_{message_id}_{uuid.uuid4().hex[:8]}.{file_extension}"
            file_path = self.temp_dir / filename

            logger.info(f"[AudioDownloader] Скачиваем в файл: {file_path}")

            # Получаем токен авторизации Avito
            try:
                auth_token = await get_avito_token()
            except Exception as e:
                logger.error(f"[AudioDownloader] Ошибка получения токена Avito: {e}")
                error = VoiceError(
                    code=VoiceErrorCodes.NETWORK_ERROR,
                    message="Не удалось получить токен авторизации Avito"
                )
                return None, error

            # Скачиваем файл
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {
                    "Authorization": f"Bearer {auth_token}",
                    "User-Agent": "AvitoAI-Assistant/1.0"
                }

                logger.info(f"[AudioDownloader] Отправляем запрос на {voice_url}")

                # Для voice_id используем POST запрос, для прямого URL - GET
                if voice_identifier.startswith('http'):
                    request_method = "GET"
                    request_data = None
                else:
                    request_method = "POST"
                    request_data = {}  # Пустое тело для POST запроса

                async with client.stream(request_method, voice_url, headers=headers, json=request_data) as response:
                    # Проверяем статус ответа
                    if response.status_code != 200:
                        logger.error(f"[AudioDownloader] HTTP ошибка: {response.status_code}")
                        error = VoiceError(
                            code=VoiceErrorCodes.DOWNLOAD_FAILED,
                            message=f"HTTP {response.status_code}: {response.reason_phrase}",
                            details={"status_code": response.status_code, "url": voice_url}
                        )
                        return None, error

                    # Проверяем размер файла из заголовков
                    content_length = response.headers.get("content-length")
                    if content_length and int(content_length) > self.max_size_bytes:
                        size_mb = int(content_length) / (1024 * 1024)
                        logger.error(f"[AudioDownloader] Файл слишком большой: {size_mb:.1f} МБ")
                        error = VoiceError(
                            code=VoiceErrorCodes.FILE_TOO_LARGE,
                            message=f"Размер файла {size_mb:.1f} МБ превышает лимит {settings.MAX_AUDIO_SIZE_MB} МБ"
                        )
                        return None, error

                    # Скачиваем файл по частям
                    total_size = 0
                    async with aiofiles.open(file_path, "wb") as file:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            total_size += len(chunk)

                            # Проверяем размер в процессе скачивания
                            if total_size > self.max_size_bytes:
                                await file.close()
                                file_path.unlink(missing_ok=True)  # Удаляем частично скачанный файл

                                size_mb = total_size / (1024 * 1024)
                                logger.error(f"[AudioDownloader] Файл превысил лимит размера: {size_mb:.1f} МБ")
                                error = VoiceError(
                                    code=VoiceErrorCodes.FILE_TOO_LARGE,
                                    message=f"Размер файла {size_mb:.1f} МБ превышает лимит {settings.MAX_AUDIO_SIZE_MB} МБ"
                                )
                                return None, error

                            await file.write(chunk)

            # Проверяем что файл успешно создан
            if not file_path.exists() or file_path.stat().st_size == 0:
                logger.error(f"[AudioDownloader] Файл не создан или пустой: {file_path}")
                error = VoiceError(
                    code=VoiceErrorCodes.DOWNLOAD_FAILED,
                    message="Файл не был скачан или оказался пустым"
                )
                return None, error

            file_size = file_path.stat().st_size
            logger.info(f"[AudioDownloader] Файл успешно скачан: {file_path} ({file_size} байт)")
            return str(file_path), None

        except httpx.TimeoutException:
            logger.error(f"[AudioDownloader] Таймаут при скачивании файла: {voice_identifier}")
            error = VoiceError(
                code=VoiceErrorCodes.PROCESSING_TIMEOUT,
                message=f"Превышен таймаут скачивания ({self.timeout}с)"
            )
            return None, error

        except httpx.RequestError as e:
            logger.error(f"[AudioDownloader] Сетевая ошибка при скачивании: {e}")
            error = VoiceError(
                code=VoiceErrorCodes.NETWORK_ERROR,
                message=f"Сетевая ошибка: {str(e)}"
            )
            return None, error

        except Exception as e:
            logger.error(f"[AudioDownloader] Неожиданная ошибка при скачивании: {e}")
            # Удаляем файл если он был создан частично
            if 'file_path' in locals() and file_path.exists():
                file_path.unlink(missing_ok=True)

            error = VoiceError(
                code=VoiceErrorCodes.DOWNLOAD_FAILED,
                message=f"Неожиданная ошибка: {str(e)}"
            )
            return None, error

    def _is_valid_url(self, url: str) -> bool:
        """Проверяет валидность URL"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def _extract_file_extension(self, url: str) -> str:
        """Извлекает расширение файла из URL"""
        try:
            parsed_url = urlparse(url)
            path = Path(parsed_url.path)
            extension = path.suffix.lower().lstrip('.')

            # Проверяем что расширение поддерживается
            if extension in [fmt.value for fmt in AudioFormat]:
                return extension
            else:
                logger.warning(f"[AudioDownloader] Неизвестное расширение '{extension}', используем 'ogg' по умолчанию")
                return "ogg"  # Avito обычно использует ogg

        except Exception:
            logger.warning(f"[AudioDownloader] Не удалось определить расширение файла, используем 'ogg'")
            return "ogg"

    async def cleanup_file(self, file_path: str) -> None:
        """Удаляет временный файл"""
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                logger.info(f"[AudioDownloader] Временный файл удален: {file_path}")
        except Exception as e:
            logger.error(f"[AudioDownloader] Ошибка при удалении файла {file_path}: {e}")

    async def cleanup_old_files(self, max_age_hours: int = 24) -> None:
        """Удаляет старые временные файлы"""
        try:
            import time
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600

            cleaned_count = 0
            for file_path in self.temp_dir.glob("*"):
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        file_path.unlink()
                        cleaned_count += 1

            if cleaned_count > 0:
                logger.info(f"[AudioDownloader] Удалено {cleaned_count} старых временных файлов")

        except Exception as e:
            logger.error(f"[AudioDownloader] Ошибка при очистке старых файлов: {e}")


# Создаем глобальный экземпляр
audio_downloader = AudioDownloader()
