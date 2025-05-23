import json
import aioredis
from app.services.logs import logger
from app.config import REDIS_HOST, REDIS_PORT

# Асинхронное подключение к Redis
async def get_redis():
    return await aioredis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", encoding='utf-8', decode_responses=True)


# Получение истории сообщений по user_id и chat_id
async def get_history(user_id, chat_id):
    redis = await get_redis()  # Подключение к Redis внутри функции
    logger.info(f"[Redis] Получение истории сообщений для пользователя {user_id}, чат {chat_id}")
    history = await redis.get(f"history:{user_id}:{chat_id}")
    if history:
        logger.info(f"[Redis] История для пользователя {user_id}, чат {chat_id} успешно получена")
        await redis.close()  # Закрытие соединения после использования
        return json.loads(history)
    else:
        logger.info(f"[Redis] История для пользователя {user_id}, чат {chat_id} не найдена")
        await redis.close()  # Закрытие соединения после использования
        return []


# Сохранение сообщения в историю (максимум 20 сообщений)
async def save_message(user_id, chat_id, role, message):
    redis = await get_redis()  # Подключение к Redis внутри функции
    logger.info(f"[Redis] Сохранение сообщения для пользователя {user_id}, чат {chat_id}, роль: {role}")
    history = await get_history(user_id, chat_id)
    if len(history) >= 20:
        logger.info(f"[Redis] История пользователя {user_id}, чат {chat_id} превышает 20 сообщений, удаление старых")
        history.pop(0)
    history.append({"role": role, "content": message})

    await redis.setex(f"history:{user_id}:{chat_id}", 86400, json.dumps(history))  # Храним 24 часа
    logger.info(f"Сообщение для пользователя {user_id}, чат {chat_id} сохранено в историю")
    await redis.close()  # Закрытие соединения после использования
    return None


# Добавление чата в список (каждый chat_id хранится 24 часа)
async def add_chat(chat_id):
    redis = await get_redis()  # Подключение к Redis внутри функции
    logger.info(f"[Redis] Добавление чата {chat_id} в список исключений")
    await redis.setex(f"chat:{chat_id}", 86400, "1")
    logger.info(f"[Redis] Чат {chat_id} успешно добавлен в список исключений")
    await redis.close()  # Закрытие соединения после использования
    return None


# Проверка наличия чата в списке
async def chat_exists(chat_id):
    redis = await get_redis()  # Подключение к Redis внутри функции
    exists = await redis.exists(f"chat:{chat_id}")
    logger.info(f"[Redis] Проверка существования чата {chat_id}: {'найден' if exists else 'не найден'}")
    await redis.close()  # Закрытие соединения после использования
    return exists


async def get_last_message(user_id, chat_id, role):
    history = await get_history(user_id, chat_id)
    if not history:
        return None  # Если истории нет, возвращаем None

    # Ищем последнее сообщение от разработчика
    for message in reversed(history):
        if message["role"] == role:
            return message["content"]

    return None  # Если сообщений от разработчика нет