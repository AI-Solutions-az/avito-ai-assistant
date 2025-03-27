from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from app.models.schemas import WebhookRequest
from app.services.avito_api import send_message, get_ad, get_user_info
from app.services.gpt import process_message
import re
from app.services.telegram_bot import send_alert
from app.redis_db import add_chat, chat_exists, get_last_message
from app.services.logs import logger
from db.chat_crud import get_chat_by_id, create_chat, update_chat
from app.services.telegram_bot import create_telegram_forum_topic, get_telegram_updates
router = APIRouter()

# Вынесение джобы в отдельную асинхронную функцию
async def process_and_send_response(message: WebhookRequest):
    # Парсинг данных из сообщения
    message_text = message.payload.value.content.text
    chat_id = message.payload.value.chat_id
    user_id = message.payload.value.user_id
    author_id = message.payload.value.author_id
    item_id = message.payload.value.item_id
    # Ссылка на диалог
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{message.payload.value.chat_id}'
    # Получение ссылки на объявление
    ad_url = await get_ad(message.payload.value.user_id, message.payload.value.item_id)
    # Получение имени пользователя и ссылки на него
    user_name, user_url = await get_user_info(message.payload.value.user_id, message.payload.value.chat_id)
    # Последнее сообщение от бота в чате
    last_assistant_message = await get_last_message(user_id, chat_id,'developer')

    # Проверка существования чата с пользователем в БД
    if not await get_chat_by_id(chat_id):
        # Создание топика в телеграм
        await create_telegram_forum_topic(f'{user_name}, {item_id}')
        # Получение номера топика
        thread_id = await get_telegram_updates()
        # Засылаем все ссылки сразу в чат
        await send_alert("Создан новый чат\n"
                         f"Клиент: {user_name}\n"
                         f"Ссылка на клиента: {user_url}\n"
                         f"Объявление: {ad_url}\n"
                         f"Ссылка на чат: {chat_url}\n", thread_id)
        # Создание чата в БД
        await create_chat(chat_id, thread_id, author_id, user_id, chat_url)
        logger.info(f'Новый чат {chat_id} создан')

    # Проверка включен ли ассистент в чате или нет. Если нет, то завершаем обработку
    chat_object = await get_chat_by_id(chat_id)
    if chat_object.under_assistant is False:
        logger.info(f'Чат бот отключен в чате {chat_id} для юзера {user_id}')
        return None

    # Проверяем от кого сообщение
    if user_id==author_id:
        # Сообщение от самого себя
        if last_assistant_message==message_text:
            # Тексты сообщений совпали
            logger.info(f'Хук на собственное сообщение в чате {chat_id}')
        else:
            # Тексты сообщений отличаются, значит подключился оператора
            # Отключаем бота в чате
            await update_chat(chat_id=chat_id, under_assistant=False)
            await send_alert("❗️К чату подключился оператор", chat_object.thread_id)
            logger.info(f'К чату {chat_id} подключился оператор')
        return None

    response = await process_message(author_id, user_id, chat_id,
                                     message_text, ad_url, user_name, chat_url)
    if response:
        logger.info(f"Ответ: {response}")
        logger.info('4. Отправка сгенерированного сообщения')
        await send_message(user_id, chat_id, response)
        logger.info("5. Отправка сообщения в телеграм канал")
        await send_alert(f"💁‍♂️ {user_name}: {message_text}\n"
                         f"🤖 Бот: {response}\n"
                         f"_____\n\n", thread_id=chat_object.thread_id)
        return None
    else:
        logger.error('Не получен ответ от модели')
        return None

@router.post("/chat")
async def chat(message: WebhookRequest, background_tasks: BackgroundTasks):
    # Добавляем выполнение кода в фоне
    background_tasks.add_task(process_and_send_response, message)

    return JSONResponse(content={"ok": True}, status_code=200)