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

    async def download_voice_file(self, voice_id: str, chat_id: str, message_id: str, user_id: int) -> Tuple[
        Optional[str], Optional[VoiceError]]:
        """
        Скачивает голосовой файл через официальный API Авито

        Args:
            voice_id: ID голосового сообщения от Avito
            chat_id: ID чата для логирования
            message_id: ID сообщения для уникального имени файла
            user_id: ID пользователя для API запроса

        Returns:
            Tuple[file_path, error]: Путь к скачанному файлу или ошибка
        """
        logger.info(f"[AudioDownloader] Начинаем скачивание голосового сообщения {voice_id}")

        try:
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

            # Шаг 1: Получаем URL голосового файла через официальный API
            voice_url_api = f"https://api.avito.ru/messenger/v1/accounts/{user_id}/getVoiceFiles"
            
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "User-Agent": "AvitoAI-Assistant/1.0",
                "Accept": "application/json"
            }
            
            params = {
                "voice_ids": voice_id
            }

            logger.info(f"[AudioDownloader] Запрашиваем URL для voice_id: {voice_id}")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(voice_url_api, headers=headers, params=params)
                
                if response.status_code != 200:
                    logger.error(f"[AudioDownloader] Ошибка получения URL: HTTP {response.status_code}")
                    error = VoiceError(
                        code=VoiceErrorCodes.DOWNLOAD_FAILED,
                        message=f"Не удалось получить URL голосового файла: HTTP {response.status_code}"
                    )
                    return None, error

                # Парсим ответ
                voice_data = response.json()
                voices_urls = voice_data.get("voices_urls", {})
                
                if voice_id not in voices_urls:
                    logger.error(f"[AudioDownloader] voice_id {voice_id} не найден в ответе API")
                    error = VoiceError(
                        code=VoiceErrorCodes.DOWNLOAD_FAILED,
                        message=f"Голосовой файл {voice_id} не найден"
                    )
                    return None, error

                voice_file_url = voices_urls[voice_id]
                logger.info(f"[AudioDownloader] Получен URL голосового файла: {voice_file_url}")

            # Шаг 2: Скачиваем файл по полученному URL
            return await self._download_file_from_url(voice_file_url, chat_id, message_id, voice_id)

        except httpx.TimeoutException:
            logger.error(f"[AudioDownloader] Таймаут при получении URL для voice_id: {voice_id}")
            error = VoiceError(
                code=VoiceErrorCodes.PROCESSING_TIMEOUT,
                message=f"Превышен таймаут запроса URL ({self.timeout}с)"
            )
            return None, error

        except Exception as e:
            logger.error(f"[AudioDownloader] Неожиданная ошибка: {e}")
            error = VoiceError(
                code=VoiceErrorCodes.DOWNLOAD_FAILED,
                message=f"Неожиданная ошибка: {str(e)}"
            )
            return None, error

    async def _download_file_from_url(self, voice_file_url: str, chat_id: str, message_id: str, voice_id: str) -> Tuple[
        Optional[str], Optional[VoiceError]]:
        """
        Скачивает файл по прямому URL
        """
        try:
            # Генерируем уникальное имя файла (Авито использует opus в mp4 контейнере)
            filename = f"{chat_id}_{message_id}_{voice_id[:8]}.mp4"
            file_path = self.temp_dir / filename

            logger.info(f"[AudioDownloader] Скачиваем файл в: {file_path}")

            # Скачиваем файл (URL от Авито уже авторизован, дополнительные заголовки не нужны)
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("GET", voice_file_url) as response:
                    # Проверяем статус ответа
                    if response.status_code != 200:
                        logger.error(f"[AudioDownloader] HTTP ошибка при скачивании: {response.status_code}")
                        error = VoiceError(
                            code=VoiceErrorCodes.DOWNLOAD_FAILED,
                            message=f"HTTP {response.status_code} при скачивании файла"
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
                                file_path.unlink(missing_ok=True)

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
            logger.error(f"[AudioDownloader] Таймаут при скачивании файла")
            error = VoiceError(
                code=VoiceErrorCodes.PROCESSING_TIMEOUT,
                message=f"Превышен таймаут скачивания ({self.timeout}с)"
            )
            return None, error

        except Exception as e:
            logger.error(f"[AudioDownloader] Ошибка при скачивании файла: {e}")
            # Удаляем файл если он был создан частично
            if 'file_path' in locals() and file_path.exists():
                file_path.unlink(missing_ok=True)

            error = VoiceError(
                code=VoiceErrorCodes.DOWNLOAD_FAILED,
                message=f"Ошибка скачивания: {str(e)}"
            )
            return None, error

    def _is_valid_url(self, url: str) -> bool:
        """Проверяет валидность URL"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

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
