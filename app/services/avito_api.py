import requests
import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")


def get_avito_token(client_id: str, client_secret: str) -> str:
    """Получение токена Avito API"""
    url = "https://api.avito.ru/token/"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }

    response = requests.post(url, headers=headers, data=data)

    if response.status_code != 200:
        print(f"Ошибка получения токена: {response.status_code}, {response.text}")
        return ""

    return response.json().get("access_token", "")


def send_message(user_id: int, chat_id: str, text: str):
    """Отправка сообщения пользователю в Avito"""
    url = f"https://api.avito.ru/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages"
    print("2.1. Запрос аксесс токена")
    access_token = get_avito_token(CLIENT_ID, CLIENT_SECRET)

    if not access_token:
        raise Exception("Не удалось получить токен Avito API")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "message": {
            "text": text
        },
        "type": "text"
    }
    print("2.2. Отправка сообщения")
    response = requests.post(url, json=payload, headers=headers)

    if response.status_code != 200:
        print(f"Ошибка при отправке сообщения: {response.status_code}, {response.text}")
        return None

    return None

def get_ad(user_id:int, item_id:int):
    """Получение информации об объявлении"""
    access_token = get_avito_token(CLIENT_ID, CLIENT_SECRET)

    if not access_token:
        raise Exception("Не удалось получить токен Avito API")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    url = f"https://api.avito.ru/core/v1/accounts/{user_id}/items/{item_id}/"
    response = requests.get(url, headers=headers)

    return response.json().get("url","")
