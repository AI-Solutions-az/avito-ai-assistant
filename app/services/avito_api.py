import logging
import requests
from functools import lru_cache
from app.config import CLIENT_ID, CLIENT_SECRET

# Настройка логирования
logger = logging.getLogger("uvicorn")

@lru_cache(maxsize=1)
def get_avito_token() -> str:
    """Получение токена Avito API с кешированием"""
    logger.info("Запрос на получение токена Avito API")
    url = "https://api.avito.ru/token/"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }

    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        token = response.json().get("access_token", "")
        logger.info("Токен Avito получен успешно")
        return token
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при получении токена Avito: {e}")
        raise

def send_message(user_id: int, chat_id: str, text: str) -> None:
    """Отправка сообщения пользователю в Avito"""
    logger.info(f"Отправка сообщения пользователю {user_id} в чат {chat_id}")
    url = f"https://api.avito.ru/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages"
    headers = {
        "Authorization": f"Bearer {get_avito_token()}",
        "Content-Type": "application/json"
    }
    payload = {"message": {"text": text}, "type": "text"}

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"Сообщение отправлено пользователю {user_id} в чат {chat_id}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        raise

def get_ad(user_id: int, item_id: int) -> str:
    """Получение информации об объявлении"""
    logger.info(f"Запрос информации об объявлении для пользователя {user_id}, item_id {item_id}")
    url = f"https://api.avito.ru/core/v1/accounts/{user_id}/items/{item_id}/"
    headers = {
        "Authorization": f"Bearer {get_avito_token()}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        ad_url = response.json().get("url", "")
        logger.info(f"Информация об объявлении получена: {ad_url}")
        return ad_url
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при получении информации об объявлении: {e}")
        raise


def get_user_info(user_id, chat_id):
    """Получение информации о чате, а через него о клиенте"""
    logger.info(f"Запрос информации об объявлении для пользователя {user_id}, item_id {chat_id}")
    url = f"https://api.avito.ru/messenger/v2/accounts/{user_id}/chats/{chat_id}"
    headers = {
        "Authorization": f"Bearer {get_avito_token()}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        user_info = response.json()
        logger.info(f"Информация об объявлении получена: {user_info}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при получении информации о пользователе: {e}")
        return None, None

    # Фильтруем пользователей, убирая "TryFashion"
    clients = [
        user for user in user_info.get("users", [])
        if user.get("public_user_profile", {}).get("name") and user["public_user_profile"]["name"] != "TryFashion"
    ]

    if not clients:
        logger.info("Клиенты, кроме TryFashion, не найдены")
        return None, None

    # Берём данные первого найденного клиента
    client = clients[0]
    user_name = client["public_user_profile"].get("name", None)
    user_url = client["public_user_profile"].get("url", None)

    if user_name is None:
        logger.info("Имя не найдено")
    if user_url is None:
        logger.info("URL не найден")

    return user_name, user_url