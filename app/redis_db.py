import redis
import json
import os
from dotenv import load_dotenv

load_dotenv()

r = redis.Redis(host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), decode_responses=True)

# Получение истории сообщений
def get_history(user_id):
    history = r.get(f"history:{user_id}")
    return json.loads(history) if history else []

# Сохранение сообщения в историю (максимум 20 сообщений)
def save_message(user_id, role, message):
    history = get_history(user_id)
    if len(history) >= 20:
        history.pop(0)
    history.append({"role": role, "content": message})
    r.setex(f"history:{user_id}", 86400, json.dumps(history))  # Храним 24 часа

# Добавление чата в список (каждый chat_id хранится 24 часа)
def add_chat(chat_id):
    r.setex(f"chat:{chat_id}", 86400, "1")

# Получение всех активных чатов
def get_chats():
    return [key.split(":")[1] for key in r.keys("chat:*")]

# Удаление чата из списка
def remove_chat(chat_id):
    r.delete(f"chat:{chat_id}")

def chat_exists(chat_id):
    return r.exists(f"chat:{chat_id}") > 0