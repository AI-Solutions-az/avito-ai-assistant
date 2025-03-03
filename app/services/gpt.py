from openai import OpenAI
import os
from app.redis_db import save_message, get_history
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Генерация ответа на сообщение клиента
def process_message(user_id: str, message: str):
    history = get_history(user_id)
    history.append({"role": "user", "content": message})
    print(history)
    response = client.chat.completions.create(model="gpt-4",
    messages={"role": "user", "content": message})

    reply = response.choices[0].message.content

    # Сохранение истории переписки
    save_message(user_id, "user", message)
    save_message(user_id, "assistant", reply)

    return reply