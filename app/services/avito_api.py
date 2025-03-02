import requests
import os
from dotenv import load_dotenv


load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET=os.getenv("CLIENT_SECRET")

def get_avito_token(client_id: str, client_secret: str):
    url = "https://api.avito.ru/token/"

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }

    response = requests.post(url, headers=headers, data=data)

    response_json = response.json()
    return response_json.get("access_token", "")

def send_message(user_id: int, chat_id: str, text: str):
    url = f"https://api.avito.ru/messenger/v3/accounts/{user_id}/chats/{chat_id}/messages"
    access_token = get_avito_token(CLIENT_ID, CLIENT_SECRET)
    print(access_token)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
                "message": {
                    "text": f"{text}"
                    },
                "type": "text"
    }

    response = requests.post(url, json=payload, headers=headers)
    print(response)

    return response.json()