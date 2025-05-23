import httpx
import asyncio
from time import time
from app.config import CLIENT_ID, CLIENT_SECRET
from app.services.logs import logger

# Глобальные переменные для кеширования токена
_avito_token = None
_token_expiry = 0
_lock = asyncio.Lock()

async def get_avito_token() -> str:
    """Получение токена Avito API с кешированием"""
    global _avito_token, _token_expiry

    async with _lock:  # Блокируем одновременные запросы на обновление токена
        if _avito_token and time() < _token_expiry:
            return _avito_token  # Возвращаем закешированный токен, если он ещё действителен

        logger.info("Запрос на получение токена Avito API")
        url = "https://api.avito.ru/token/"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, data=data)
                response.raise_for_status()
                token_data = response.json()
                _avito_token = token_data.get("access_token", "")
                _token_expiry = time() + token_data.get("expires_in", 3600) - 60  # Минус 60 сек для надёжности
                logger.info("Токен Avito получен успешно")
                return _avito_token
        except httpx.RequestError as e:
            logger.error(f"Ошибка при получении токена Avito: {e}")
            raise

async def send_message(user_id: int, chat_id: str, text: str) -> None:
    """Отправка сообщения пользователю в Avito"""
    logger.info(f"Отправка сообщения пользователю {user_id} в чат {chat_id}")
    url = f"https://api.avito.ru/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages"
    headers = {
        "Authorization": f"Bearer {await get_avito_token()}",
        "Content-Type": "application/json"
    }
    payload = {"message": {"text": text}, "type": "text"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"Сообщение отправлено пользователю {user_id} в чат {chat_id}")
    except httpx.RequestError as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        raise

async def get_ad(user_id: int, item_id: int) -> str:
    """Получение информации об объявлении"""
    logger.info(f"[API] Запрос информации об объявлении для пользователя {user_id}, item_id {item_id}")
    url = f"https://api.avito.ru/core/v1/accounts/{user_id}/items/{item_id}/"
    headers = {
        "Authorization": f"Bearer {await get_avito_token()}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            ad_url = response.json().get("url", "")
            logger.info(f"API] Информация об объявлении получена: {ad_url}")
            return ad_url
    except httpx.RequestError as e:
        logger.error(f"API] Ошибка при получении информации об объявлении: {e}")
        raise

async def get_user_info(user_id, chat_id):
    """Получение информации о чате, а через него о клиенте"""
    logger.info(f"[API] Запрос информации о чате для пользователя {user_id}, chat_id {chat_id}")
    url = f"https://api.avito.ru/messenger/v2/accounts/{user_id}/chats/{chat_id}"
    headers = {
        "Authorization": f"Bearer {await get_avito_token()}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            user_info = response.json()
            logger.info(f"[API] Информация о пользователе получена: {user_info}")
    except httpx.RequestError as e:
        logger.error(f"[API] Ошибка при получении информации о пользователе: {e}")
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