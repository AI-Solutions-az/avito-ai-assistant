# app/services/client_telegram_notifier.py

import asyncio
from aiogram import Bot
from aiogram.types import ForumTopicCreated
from app.services.logs import logger
from db.client_crud import get_client_by_avito_id

# Store bot instances for different clients
_client_bots = {}


async def get_client_bot(client_avito_id: str):
    """Get or create a bot instance for the specific client"""
    if client_avito_id in _client_bots:
        return _client_bots[client_avito_id]

    # Get client configuration
    client = await get_client_by_avito_id(client_avito_id)
    if not client or not client.telegram_bot_token:
        logger.error(f"Telegram configuration missing for client {client_avito_id}")
        return None

    # Create and cache bot instance
    bot = Bot(token=client.telegram_bot_token)
    _client_bots[client_avito_id] = bot
    return bot


async def send_client_alert(message: str, client_avito_id: str, thread_id: int = None):
    """Send alert message using client-specific bot and chat"""
    logger.info(f"Sending Telegram alert for client {client_avito_id}")

    client = await get_client_by_avito_id(client_avito_id)
    if not client:
        logger.error(f"Client {client_avito_id} not found")
        return

    if not client.telegram_chat_id:
        logger.error(f"Telegram chat ID missing for client {client_avito_id}")
        return

    bot = await get_client_bot(client_avito_id)
    if not bot:
        return

    try:
        # Use client-specific thread_id if provided, otherwise use client's default
        target_thread_id = thread_id or client.telegram_thread_id

        if target_thread_id:
            await bot.send_message(
                chat_id=client.telegram_chat_id,
                text=message,
                message_thread_id=target_thread_id
            )
        else:
            await bot.send_message(chat_id=client.telegram_chat_id, text=message)

        logger.info(f"Alert sent successfully for client {client_avito_id}")
    except Exception as e:
        logger.error(f"Error sending Telegram alert for client {client_avito_id}: {e}")
        raise


async def create_client_telegram_forum_topic(topic_name: str, client_avito_id: str):
    """Create a forum topic using client-specific bot"""
    logger.info(f"Creating Telegram forum topic for client {client_avito_id}: {topic_name}")

    client = await get_client_by_avito_id(client_avito_id)
    if not client or not client.telegram_chat_id:
        logger.error(f"Telegram configuration missing for client {client_avito_id}")
        return None

    bot = await get_client_bot(client_avito_id)
    if not bot:
        return None

    try:
        response = await bot.create_forum_topic(chat_id=client.telegram_chat_id, name=topic_name)
        logger.info(f"Forum topic created successfully for client {client_avito_id}")
        return response.message_thread_id
    except Exception as e:
        logger.error(f"Error creating forum topic for client {client_avito_id}: {e}")
        raise


async def cleanup_client_bots():
    """Cleanup all bot sessions"""
    for client_id, bot in _client_bots.items():
        try:
            await bot.session.close()
            logger.info(f"Bot session closed for client {client_id}")
        except Exception as e:
            logger.error(f"Error closing bot session for client {client_id}: {e}")
    _client_bots.clear()