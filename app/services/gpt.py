from openai import OpenAI
import os
from app.redis_db import save_message, get_history
from dotenv import load_dotenv
from app.config import prompt, warehouse

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Инструкция бота
instructions = {"role": "developer", "content": f"{prompt}+{warehouse}"}

# Генерация ответа на сообщение клиента
def process_message(user_id: str, message: str):

    history = get_history(user_id)
    history.append({"role": "user", "content": message})

    messages = history + [instructions]  # Создаём новый список с дополнительным элементом

    print("1.1. Отправка запрос в ChatGPT")
    response = client.chat.completions.create(model="gpt-4",
    messages=messages)

    reply = response.choices[0].message.content

    print("1.2. Сохранение истории в редис")

    save_message(user_id, "user", message)
    save_message(user_id, "assistant", reply)

    return reply