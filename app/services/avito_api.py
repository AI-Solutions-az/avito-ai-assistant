import logging
import aiohttp
import asyncio
from functools import lru_cache
from app.config import CLIENT_ID, CLIENT_SECRET

# Настройка логирования
logger = logging.getLogger("uvicorn")

# Кеширование токена в переменной
_token = None

async def fetch_avito_token() -> str:
    """Получение токена Avito API с кешированием"""
    global _token
    if _token:
        return _token

    logger.info("Запрос на получение токена Avito API")
    url = "https://api.avito.ru/token/"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, data=data) as response:
                response.raise_for_status()
                result = await response.json()
                _token = result.get("access_token", "")
                logger.info("Токен Avito получен успешно")
                return _token
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка при получении токена Avito: {e}")
            raise

async def send_message(user_id: int, chat_id: str, text: str) -> None:
    """Отправка сообщения пользователю в Avito"""
    logger.info(f"Отправка сообщения пользователю {user_id} в чат {chat_id}")
    url = f"https://api.avito.ru/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages"
    headers = {
        "Authorization": f"Bearer {await fetch_avito_token()}",
        "Content-Type": "application/json"
    }
    payload = {"message": {"text": text}, "type": "text"}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                response.raise_for_status()
                logger.info(f"Сообщение отправлено пользователю {user_id} в чат {chat_id}")
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка при отправке сообщения: {e}")
            raise

async def get_ad(user_id: int, item_id: int) -> str:
    """Получение информации об объявлении"""
    logger.info(f"Запрос информации об объявлении для пользователя {user_id}, item_id {item_id}")
    url = f"https://api.avito.ru/core/v1/accounts/{user_id}/items/{item_id}/"
    headers = {
        "Authorization": f"Bearer {await fetch_avito_token()}",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                ad_url = (await response.json()).get("url", "")
                logger.info(f"Информация об объявлении получена: {ad_url}")
                return ad_url
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка при получении информации об объявлении: {e}")
            raise

async def get_user_info(user_id, chat_id):
    """Получение информации о чате, а через него о клиенте"""
    logger.info(f"Запрос информации об объявлении для пользователя {user_id}, item_id {chat_id}")
    url = f"https://api.avito.ru/messenger/v2/accounts/{user_id}/chats/{chat_id}"
    headers = {
        "Authorization": f"Bearer {await fetch_avito_token()}",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                user_info = await response.json()
                logger.info(f"Информация об пользователе получена: {user_info}")
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка при получении информации о пользователе: {e}")
            return None, None

    # Получаем первый элемент списка для имени и URL
    user_name = next((user['name'] for user in user_info['users'] if user['name'] != 'TryFashion'), None)
    user_url = next(
        (user['public_user_profile']['url'] for user in user_info['users'] if user['name'] != 'TryFashion'), None)

    if user_name is None:
        logger.info("Имя не найдено")
    if user_url is None:
        logger.info("URL не найден")

    return user_name, user_url