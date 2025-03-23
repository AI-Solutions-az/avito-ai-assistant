import logging
import redis
import json
import os
from dotenv import load_dotenv

# Настройка логирования
logger = logging.getLogger("uvicorn")

load_dotenv()

r = redis.Redis(host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), decode_responses=True)


# Получение истории сообщений по user_id и chat_id
def get_history(user_id, chat_id):
    logger.info(f"Получение истории сообщений для пользователя {user_id}, чат {chat_id}")
    history = r.get(f"history:{user_id}:{chat_id}")
    if history:
        logger.info(f"История для пользователя {user_id}, чат {chat_id} успешно получена")
        return json.loads(history)
    else:
        logger.info(f"История для пользователя {user_id}, чат {chat_id} не найдена")
        return []


# Сохранение сообщения в историю (максимум 20 сообщений)
def save_message(user_id, chat_id, role, message):
    logger.info(f"Сохранение сообщения для пользователя {user_id}, чат {chat_id}, роль: {role}")
    history = get_history(user_id, chat_id)
    if len(history) >= 20:
        logger.info(f"История пользователя {user_id}, чат {chat_id} превышает 20 сообщений, удаление старых")
        history.pop(0)
    history.append({"role": role, "content": message})

    r.setex(f"history:{user_id}:{chat_id}", 86400, json.dumps(history))  # Храним 24 часа
    logger.info(f"Сообщение для пользователя {user_id}, чат {chat_id} сохранено в историю")


# Добавление чата в список (каждый chat_id хранится 24 часа)
def add_chat(chat_id):
    logger.info(f"Добавление чата {chat_id} в список исключений")
    r.setex(f"chat:{chat_id}", 86400, "1")
    logger.info(f"Чат {chat_id} успешно добавлен в список исключений")


# Проверка наличия чата в списке
def chat_exists(chat_id):
    exists = r.exists(f"chat:{chat_id}") > 0
    logger.info(f"Проверка существования чата {chat_id}: {'найден' if exists else 'не найден'}")
    return exists