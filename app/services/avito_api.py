import requests
import os
from dotenv import load_dotenv
from functools import lru_cache

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")


@lru_cache(maxsize=1)
def get_avito_token() -> str:
    """Получение токена Avito API с кешированием"""
    url = "https://api.avito.ru/token/"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }

    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()

    return response.json().get("access_token", "")


def send_message(user_id: int, chat_id: str, text: str) -> None:
    """Отправка сообщения пользователю в Avito"""
    url = f"https://api.avito.ru/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages"
    headers = {
        "Authorization": f"Bearer {get_avito_token()}",
        "Content-Type": "application/json"
    }
    payload = {"message": {"text": text}, "type": "text"}

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()


def get_ad(user_id: int, item_id: int) -> str:
    """Получение информации об объявлении"""
    url = f"https://api.avito.ru/core/v1/accounts/{user_id}/items/{item_id}/"
    headers = {
        "Authorization": f"Bearer {get_avito_token()}",
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json().get("url", "")