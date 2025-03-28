from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from app.models.schemas import WebhookRequest
from app.services.avito_api import send_message, get_ad, get_user_info
from app.services.gpt import process_message
from app.services.telegram_notifier import send_alert
from app.services.logs import logger
from db.chat_crud import get_chat_by_id, create_chat, update_chat
from app.services.telegram_notifier import create_telegram_forum_topic
from db.messages_crud import get_latest_message_by_chat_id
import asyncio

router = APIRouter()

# Очередь сообщений
message_queues = {}


async def message_collector(chat_id, message: WebhookRequest):
    """ Собирает сообщения для указанного чата и отправляет их на обработку разом """
    if chat_id not in message_queues:
        message_queues[chat_id] = asyncio.Queue()

    queue = message_queues[chat_id]
    await queue.put(message)

    # Если уже запущена задача обработки, выходим
    if queue.qsize() > 1:
        return

    await asyncio.sleep(8)  # Ждем 8 секунд

    messages = []
    while not queue.empty():
        messages.append(await queue.get())

    # Склеиваем все сообщения
    combined_message = " ".join(msg.payload.value.content.text for msg in messages)

    # Обновляем текст последнего сообщения
    messages[-1].payload.value.content.text = combined_message

    # Отправляем на обработку
    await process_and_send_response(messages[-1])


async def process_and_send_response(message: WebhookRequest):
    """ Обрабатывает сообщение и отправляет ответ """
    logger.info(f'[Logic] Обработка запроса от {message.payload.value.author_id}')
    message_text = message.payload.value.content.text
    chat_id = message.payload.value.chat_id
    user_id = message.payload.value.user_id
    author_id = message.payload.value.author_id
    item_id = message.payload.value.item_id

    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    ad_url = await get_ad(user_id, item_id)
    user_name, user_url = await get_user_info(user_id, chat_id)
    last_message = await get_latest_message_by_chat_id(chat_id)
    chat_object = await get_chat_by_id(chat_id)

    if not chat_object:
        logger.info("[Logic] Чат отсутствует")
        thread_id = await create_telegram_forum_topic(f'{user_name}, {item_id}')
        await send_alert(f"Создан новый чат\nКлиент: {user_name}\nСсылка на клиента: {user_url}\n"
                         f"Объявление: {ad_url}\nСсылка на чат: {chat_url}\n", thread_id)
        await create_chat(chat_id, thread_id, author_id, user_id, chat_url)

    if chat_object.under_assistant is False:
        logger.info(f'[Logic] Чат бот отключен в чате {chat_id} для юзера {user_id}')
        return None

    if user_id == author_id:
        if last_message == message_text:
            logger.info(f'[Logic] Хук на собственное сообщение в чате {chat_id}')
        else:
            await update_chat(chat_id=chat_id, under_assistant=False)
            await send_alert("❗️К чату подключился оператор", chat_object.thread_id)
            logger.info(f'[Logic] К чату {chat_id} подключился оператор')
        return None

    response = await process_message(author_id, user_id, chat_id, message_text, ad_url, user_name, chat_url)

    if response:
        logger.info(f"[Logic] Ответ: {response}")
        await send_message(user_id, chat_id, response)
        await send_alert(f"💁‍♂️ {user_name}: {message_text}\n🤖 Бот: {response}\n_____\n\n",
                         thread_id=chat_object.thread_id)
    else:
        logger.error('[Logic] Не получен ответ от модели')


@router.post("/chat")
async def chat(message: WebhookRequest, background_tasks: BackgroundTasks):
    """ Принимает сообщение и добавляет его в очередь обработки """
    chat_id = message.payload.value.chat_id
    background_tasks.add_task(message_collector, chat_id, message)
    return JSONResponse(content={"ok": True}, status_code=200)