# app/routes/chat.py - Updated version

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from app.models.schemas import WebhookRequest
from app.services.avito_api import send_message, get_ad, get_user_info
from app.services.client_openai_assistant import client_assistant_manager
from app.services.client_telegram_notifier import send_client_alert, create_client_telegram_forum_topic
from app.services.logs import logger
from db.chat_crud import get_chat_by_id, create_chat, update_chat
from db.messages_crud import get_latest_message_by_chat_id
from db.client_crud import get_client_by_avito_id
import asyncio

router = APIRouter()

# Message queues and processing tasks
message_queues = {}
processing_tasks = {}


async def determine_client_from_message(message: WebhookRequest):
    """
    Determine which client this message belongs to based on the author_id (Avito account)
    This function should be customized based on how you map Avito accounts to clients
    """
    author_id = message.payload.value.author_id

    # Option 1: Direct mapping - if author_id IS the client_id
    client = await get_client_by_avito_id(str(author_id))
    if client:
        return str(author_id)

    # Option 2: You could store a mapping table if needed
    # For now, we'll log and return None if no client found
    logger.error(f"No client found for author_id: {author_id}")
    return None


async def message_collector(chat_id, message: WebhookRequest):
    """Add message to queue and reset waiting timer"""
    message_text = message.payload.value.content.text
    user_id = message.payload.value.user_id
    author_id = message.payload.value.author_id
    item_id = message.payload.value.item_id

    # Determine which client this message belongs to
    client_avito_id = await determine_client_from_message(message)
    if not client_avito_id:
        logger.error(f"Cannot determine client for message in chat {chat_id}")
        return None

    # Create chat URL
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'

    # Get advertisement URL using client-specific API
    ad_url = await get_ad(user_id, item_id, client_avito_id)

    # Get user information using client-specific API
    user_name, user_url = await get_user_info(user_id, chat_id, client_avito_id)

    # Check if chat exists in database
    if not await get_chat_by_id(chat_id):
        logger.info(f"Chat {chat_id} not found, creating new chat for client {client_avito_id}")

        # Create forum topic using client-specific Telegram
        thread_id = await create_client_telegram_forum_topic(f'{user_name}, {item_id}', client_avito_id)

        # Store client_avito_id in the client_db_id field for now (you might want to store the actual DB ID)
        client = await get_client_by_avito_id(client_avito_id)
        client_db_id = client.id if client else None

        await create_chat(chat_id, thread_id, author_id, user_id, chat_url, client_db_id=client_db_id)

        await send_client_alert(
            f"Создан новый чат\nКлиент: {user_name}\nСсылка на клиента: {user_url}\n"
            f"Объявление: {ad_url}\nСсылка на чат: {chat_url}\n",
            client_avito_id,
            thread_id
        )
        logger.info(f"Created new chat {chat_id} for client {client_avito_id}")

    chat_object = await get_chat_by_id(chat_id)

    if chat_object.under_assistant is False:
        logger.info(f'Chat bot disabled for chat {chat_id}, client {client_avito_id}')
        return None

    # Check if this is operator's own message
    if user_id == author_id:
        last_message = await get_latest_message_by_chat_id(chat_id)
        if last_message == message_text:
            logger.info(f'Webhook triggered by own message in chat {chat_id}')
        else:
            await update_chat(chat_id=chat_id, under_assistant=False)
            await send_client_alert("❗️К чату подключился оператор", client_avito_id, chat_object.thread_id)
            logger.info(f'Operator connected to chat {chat_id}')
        return None

    # Add to message queue
    if chat_id not in message_queues:
        message_queues[chat_id] = asyncio.Queue()

    queue = message_queues[chat_id]
    await queue.put((message, client_avito_id))

    # Reset processing timer
    if chat_id in processing_tasks and not processing_tasks[chat_id].done():
        processing_tasks[chat_id].cancel()

    # Start new timer
    processing_tasks[chat_id] = asyncio.create_task(
        process_queue_after_delay(chat_id, author_id, user_id, message_text, ad_url, user_name, chat_object.thread_id,
                                  client_avito_id)
    )


async def process_queue_after_delay(chat_id, author_id, user_id, message_text, ad_url, user_name, thread_id,
                                    client_avito_id):
    """Wait 8 seconds without new messages, then process queue"""
    try:
        logger.info(f"Waiting 8 seconds for chat {chat_id}, client {client_avito_id}")
        await asyncio.sleep(8)
    except asyncio.CancelledError:
        return

    queue = message_queues.get(chat_id)
    if not queue:
        return

    messages = []
    while not queue.empty():
        message_data = await queue.get()
        messages.append(message_data[0])  # message_data is (message, client_avito_id)

    # Combine all messages
    combined_message = " ".join(msg.payload.value.content.text for msg in messages)

    # Process and send response
    await process_and_send_response(combined_message, chat_id, author_id, user_id, ad_url, user_name, thread_id,
                                    client_avito_id)


async def process_and_send_response(combined_message, chat_id, author_id, user_id, ad_url, user_name, thread_id,
                                    client_avito_id):
    """Process message and send response using client-specific services"""
    logger.info(f'Processing request for chat {chat_id}, client {client_avito_id}')

    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'

    # Process message using client-specific assistant
    response = await client_assistant_manager.process_message(
        client_id=author_id,
        user_id=user_id,
        chat_id=chat_id,
        message=combined_message,
        ad_url=ad_url,
        client_name=user_name,
        chat_url=chat_url,
        client_avito_id=client_avito_id
    )

    if response:
        logger.info(f"Chat {chat_id}, client {client_avito_id}\nResponse: {response}")

        # Send message using client-specific API
        await send_message(user_id, chat_id, response, client_avito_id)

        # Send alert using client-specific Telegram
        await send_client_alert(
            f"💁‍♂️ {user_name}: {combined_message}\n🤖 Бот: {response}\n_____\n\n",
            client_avito_id,
            thread_id
        )
    else:
        logger.error(f'No response from model for chat {chat_id}, client {client_avito_id}')


@router.post("/chat")
async def chat(message: WebhookRequest, background_tasks: BackgroundTasks):
    """Accept message and add to processing queue"""
    chat_id = message.payload.value.chat_id
    background_tasks.add_task(message_collector, chat_id, message)
    return JSONResponse(content={"ok": True}, status_code=200)