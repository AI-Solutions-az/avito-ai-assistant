import logging
from openai import OpenAI
import os
from app.redis_db import save_message, get_history
from dotenv import load_dotenv
from app.config import prompt
from app.services.google_sheets_api import fetch_google_sheet_stock, get_knowledge_base
from app.services.telegram_bot import send_alert

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Настройка логирования
logger = logging.getLogger("uvicorn")

# Генерация ответа на сообщение клиента
def process_message(user_id: str, message: str, ad_url):
    logger.info(f"Получено сообщение от пользователя {user_id}: {message}")

    history = get_history(user_id)
    history.append({"role": "user", "content": message})
    # Получение информации по объявлению из базы знаний
    stock = fetch_google_sheet_stock(ad_url)
    # Выключаем бота, если не нашли объявление в базе знаний и отправляем уведомление об этом
    if not stock:
        # send_alert(f'Невозможно найти объявление {ad_url} в базе знаний')
        return None
    # Запрос базы знаний
    knowledge_base = get_knowledge_base()

    # Инструкция бота
    instructions = {"role": "developer", "content": f"{prompt}\n"
                                                    f"# INFORMATION: {stock}"
                                                    f"# COMMON QUESTIONS: {knowledge_base}"}

    messages = history + [instructions]  # Создаём новый список с дополнительным элементом

    logger.info("1.1. Отправка запроса в ChatGPT")
    response = client.chat.completions.create(model="gpt-4o-mini", messages=messages)

    reply = response.choices[0].message.content

    logger.info("1.2. Сохранение истории в редис")
    save_message(user_id, "user", message)
    save_message(user_id, "assistant", reply)

    return reply