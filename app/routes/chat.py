from datetime import datetime, time
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from app.models.schemas import WebhookRequest
from app.services.avito_api import send_message, get_ad, get_user_info
from app.services.gpt import process_message
from app.services.telegram_notifier import send_alert
from app.services.logs import logger
from app.config import Settings
from db.chat_crud import get_chat_by_id, create_chat, update_chat
from app.services.telegram_notifier import create_telegram_forum_topic
from db.messages_crud import get_latest_message_by_chat_id

import asyncio

router = APIRouter()

# Очередь сообщений и задачи ожидания
message_queues = {}
processing_tasks = {}


async def message_collector(chat_id, message: WebhookRequest):
    """ Добавляет сообщение в очередь и сбрасывает таймер ожидания """
    message_text = message.payload.value.content.text
    user_id = message.payload.value.user_id
    author_id = message.payload.value.author_id
    item_id = message.payload.value.item_id
    if str(message.payload.value.author_id) == "0":
        logger.info(f"Пропуск системного сообщения...")
        return None

    # Создание ссылки на чат
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'

    # Получение ссылки на объявление, по которому было сообщение
    ad_url = await get_ad(user_id, item_id)

    # Получение информации по пользователю
    user_name, user_url = await get_user_info(user_id, chat_id)
    current_time = datetime.now().time()
    is_night_time = time(22, 0) <= current_time or current_time <= time(10, 0)

    # Проверка существования чата в БД AIvito
    if not await get_chat_by_id(chat_id):
        logger.info(f"[Logic] Чат {chat_id} отсутствует")
        thread_id = await create_telegram_forum_topic(f'{user_name}, {item_id}')
        await create_chat(chat_id, thread_id, author_id, user_id, chat_url, under_assistant=is_night_time)
        await send_alert(f"Создан новый чат\nКлиент: {user_name}\nСсылка на клиента: {user_url}\n"
                         f"Объявление: {ad_url}\nСсылка на чат: {chat_url}\n", thread_id)
        logger.info(f"[Logic] Создан новый чат {chat_id}")

    chat_object = await get_chat_by_id(chat_id)

    if chat_object.under_assistant is False:
        logger.info(f'[Logic] Чат бот отключен в чате {chat_id} для юзера {user_id}')
        return None

    if Settings.Working_time_logic:
        # Дневной режим (10:00 - 22:00)
        if not is_night_time:
            # Если сообщение от менеджера - ставим метку
            if str(author_id) == str(user_id):
                await update_chat(
                    chat_id=chat_id,
                    under_assistant=False  # Менеджер работает самостоятельно
                )
                logger.info(f"[Logic] Менеджер активен в чате {chat_id}")
            logger.info(f"[Logic] Получено сообщение от пользователя в нерабочее время {chat_id}")
            return None  # Бот не обрабатывает сообщения днем

        # Ночной режим (22:00 - 10:00)
        else:
            # Создание/обновление чата в БД (обязательно для всех сообщений)
            if user_id == author_id:
                last_message = await get_latest_message_by_chat_id(chat_id)
                if last_message == message_text:
                    logger.info(f'[Logic] Хук на собственное сообщение в чате {chat_id}')
                else:
                    await update_chat(chat_id=chat_id, under_assistant=False)
                    await send_alert("❗️К чату подключился оператор", chat_object.thread_id)
                    logger.info(f'[Logic] К чату {chat_id} подключился оператор')
                return None

    if user_id == author_id:
        last_message = await get_latest_message_by_chat_id(chat_id)
        if last_message == message_text:
            logger.info(f'[Logic] Хук на собственное сообщение в чате {chat_id}')
        else:
            await update_chat(chat_id=chat_id, under_assistant=False)
            await send_alert("❗️К чату подключился оператор", chat_object.thread_id)
            logger.info(f'[Logic] К чату {chat_id} подключился оператор')
        return None

    # Проверка тут, так как нельзя ставить очередь на собственное сообщение
    if chat_id not in message_queues:
        message_queues[chat_id] = asyncio.Queue()

    queue = message_queues[chat_id]
    await queue.put(message)

    # Сбрасываем существующую задачу ожидания, если она есть
    if chat_id in processing_tasks and not processing_tasks[chat_id].done():
        processing_tasks[chat_id].cancel()

    # Запускаем новый таймер
    processing_tasks[chat_id] = asyncio.create_task(process_queue_after_delay(chat_id, author_id, user_id, message_text, ad_url, user_name, chat_object.thread_id))


async def process_queue_after_delay(chat_id, author_id, user_id, message_text, ad_url, user_name, thread_id):
    """ Ждет 20 секунд без новых сообщений, затем обрабатывает очередь """
    try:
        logger.info(f"[Queue] Ожидание 20 секунд для {chat_id}")
        await asyncio.sleep(20)  # Ожидание без сброса
    except asyncio.CancelledError:
        return  # Таймер был сброшен новым сообщением

    queue = message_queues.get(chat_id)
    if not queue:
        return

    messages = []
    while not queue.empty():
        messages.append(await queue.get())

    # Склеиваем все сообщения
    combined_message = " ".join(msg.payload.value.content.text for msg in messages)

    # Отправляем на обработку
    await process_and_send_response(combined_message, chat_id, author_id, user_id, ad_url, user_name, thread_id)


async def process_and_send_response(combined_message, chat_id, author_id, user_id, ad_url, user_name, thread_id):
    """ Обрабатывает сообщение и отправляет ответ """
    logger.info(f'[Logic] Обработка запроса от {chat_id}')

    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    response = await process_message(client_id=author_id, user_id=user_id, chat_id=chat_id, message=combined_message, ad_url=ad_url, client_name=user_name, chat_url=chat_url)

    if response == "__emoji_only__":
        logger.info(f"[Logic] Пропущено сообщение только из эмодзи в чате {chat_id}")
    elif response is None:
        logger.error(f'[Logic] Не получен ответ от модели в чате {chat_id}')
    else:
        logger.info(f"[Logic] Чат {chat_id}\n"
                    f"Ответ модели: {response}")
        await send_message(user_id, chat_id, response)
        await send_alert(f"💁‍♂️ {user_name}: {combined_message}\n🤖 Бот: {response}\n_____\n\n",
                         thread_id=thread_id)


@router.post("/chat")
async def chat(message: WebhookRequest, background_tasks: BackgroundTasks):
    """ Принимает сообщение и добавляет его в очередь обработки """
    chat_id = message.payload.value.chat_id
    background_tasks.add_task(message_collector, chat_id, message)
    return JSONResponse(content={"ok": True}, status_code=200)
