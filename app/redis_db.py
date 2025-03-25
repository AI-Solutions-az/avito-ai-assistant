import logging
import aioredis
import json
import os
from dotenv import load_dotenv

# Настройка логирcования
logger = logging.getLogger("uvicorn")

load_dotenv()

# Инициализация асинхронного Redis клиента
r = aioredis.from_url(f"redis://{os.getenv('REDIS_HOST')}:{os.getenv('REDIS_PORT')}", decode_responses=True)


# Получение истории сообщений по user_id и chat_id
async def get_history(user_id, chat_id):
    logger.info(f"Получение истории сообщений для пользователя {user_id}, чат {chat_id}")
    history = await r.get(f"history:{user_id}:{chat_id}")
    if history:
        logger.info(f"История для пользователя {user_id}, чат {chat_id} успешно получена")
        return json.loads(history)
    else:
        logger.info(f"История для пользователя {user_id}, чат {chat_id} не найдена")
        return []


# Сохранение сообщения в историю (максимум 20 сообщений)
async def save_message(user_id, chat_id, role, message):
    logger.info(f"Сохранение сообщения для пользователя {user_id}, чат {chat_id}, роль: {role}")
    history = await get_history(user_id, chat_id)
    if len(history) >= 20:
        logger.info(f"История пользователя {user_id}, чат {chat_id} превышает 20 сообщений, удаление старых")
        history.pop(0)
    history.append({"role": role, "content": message})

    await r.setex(f"history:{user_id}:{chat_id}", 86400, json.dumps(history))  # Храним 24 часа
    logger.info(f"Сообщение для пользователя {user_id}, чат {chat_id} сохранено в историю")


# Добавление чата в список (каждый chat_id хранится 24 часа)
async def add_chat(chat_id):
    logger.info(f"Добавление чата {chat_id} в список исключений")
    await r.setex(f"chat:{chat_id}", 86400, "1")
    logger.info(f"Чат {chat_id} успешно добавлен в список исключений")


# Проверка наличия чата в списке
async def chat_exists(chat_id):
    exists = await r.exists(f"chat:{chat_id}")
    logger.info(f"Проверка существования чата {chat_id}: {'найден' if exists else 'не найден'}")
    return exists