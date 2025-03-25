import requests
import json
from app.config import SOURCE_TOKEN, INGESTING_HOST

def send_log(message: str):
    """
    Отправляет лог-сообщение на указанный сервер логирования.

    :param ingesting_host: Хост для логирования (например, "in.logtail.com").
    :param source_token: Токен аутентификации для Logtail.
    :param message: Основное текстовое сообщение лога.
    :param nested: Дополнительные данные в виде словаря (по умолчанию None).
    """
    url = f"https://{INGESTING_HOST}"
    headers = {
        "Authorization": f"Bearer {SOURCE_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "message": message,
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()  # Проверка успешности запроса
        print(f"✅ Лог отправлен: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка при отправке лога: {e}")