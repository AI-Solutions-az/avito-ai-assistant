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


async def get_ad(user_id: int, item_id: int, max_retries: int = 3):
    """
    Получение информации об объявлении с обработкой таймаутов и retry

    Args:
        user_id: ID пользователя
        item_id: ID объявления
        max_retries: Максимальное количество попыток (по умолчанию 3)

    Returns:
        URL объявления или None в случае неустранимой ошибки
    """
    logger.info(f"[API] Запрос информации об объявлении для пользователя {user_id}, item_id {item_id}")

    url = f"https://api.avito.ru/core/v1/accounts/{user_id}/items/{item_id}/"

    # Настройка таймаутов
    timeout = httpx.Timeout(
        connect=10.0,  # таймаут на подключение
        read=30.0,  # таймаут на чтение ответа
        write=10.0,  # таймаут на запись
        pool=10.0  # таймаут на получение соединения из пула
    )

    # Настройка retry для разных типов ошибок
    retry_delays = [1, 2, 4]  # экспоненциальная задержка

    for attempt in range(max_retries):
        try:
            headers = {
                "Authorization": f"Bearer {await get_avito_token()}",
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                ad_data = response.json()
                ad_url = ad_data.get("url", "")

                logger.info(f"[API] Информация об объявлении получена: {ad_url}")
                return ad_url

        except httpx.ConnectTimeout:
            logger.warning(f"[API] Таймаут подключения (попытка {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                delay = retry_delays[attempt] if attempt < len(retry_delays) else retry_delays[-1]
                await asyncio.sleep(delay)
                continue
            else:
                logger.error(f"[API] Не удалось подключиться к API после {max_retries} попыток")
                return None

        except httpx.ReadTimeout:
            logger.warning(f"[API] Таймаут чтения ответа (попытка {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                delay = retry_delays[attempt] if attempt < len(retry_delays) else retry_delays[-1]
                await asyncio.sleep(delay)
                continue
            else:
                logger.error(f"[API] Не удалось получить ответ от API после {max_retries} попыток")
                return None

        except httpx.HTTPStatusError as e:
            # Для HTTP ошибок 4xx не делаем retry (ошибки клиента)
            if 400 <= e.response.status_code < 500:
                logger.error(f"[API] HTTP ошибка клиента {e.response.status_code}: {e.response.text}")
                return None
            # Для 5xx ошибок делаем retry
            else:
                logger.warning(
                    f"[API] HTTP ошибка сервера {e.response.status_code} (попытка {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt] if attempt < len(retry_delays) else retry_delays[-1]
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"[API] Серверная ошибка после {max_retries} попыток: {e}")
                    return None

        except httpx.NetworkError as e:
            logger.warning(f"[API] Сетевая ошибка (попытка {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                delay = retry_delays[attempt] if attempt < len(retry_delays) else retry_delays[-1]
                await asyncio.sleep(delay)
                continue
            else:
                logger.error(f"[API] Сетевая ошибка после {max_retries} попыток: {e}")
                return None

        except Exception as e:
            logger.error(f"[API] Неожиданная ошибка при получении информации об объявлении: {e}")
            return None

    return None

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