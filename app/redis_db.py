import redis
import json
import os
from dotenv import load_dotenv

load_dotenv()

r = redis.Redis(host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), decode_responses=True)

# Получение истории сообщений
def get_history(user_id):
    history = r.get(user_id)
    return json.loads(history) if history else []

# Сохранение сообщения в историю
def save_message(user_id, role, message):
    history = get_history(user_id)
    history.append({"role": role, "content": message})
    r.set(user_id, json.dumps(history), ex=86400)  # Храним 24 часа