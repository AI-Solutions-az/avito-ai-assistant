# app/services/telegram_bot.py - Transitional version (backward compatible)

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from app.config import TELEGRAM_BOT_TOKEN
from app.services.logs import logger
from db.chat_crud import update_chat_by_thread

# Keep the old global bot for backward compatibility
bot = None


async def turn_on(message: Message) -> None:
    """Command /turn_on — connects bot to dialogue."""
    thread_id = message.message_thread_id
    await update_chat_by_thread(thread_id, True)
    await message.answer("Бот подключен к диалогу")


async def turn_off(message: Message) -> None:
    """Command /turn_off — disconnects bot from dialogue."""
    thread_id = message.message_thread_id
    await update_chat_by_thread(thread_id, False)
    await message.answer("Бот отключен от диалогу")


async def start_bot() -> None:
    """Start the admin bot."""
    global bot

    # First try to use the legacy token from environment
    if TELEGRAM_BOT_TOKEN:
        logger.info("Using legacy Telegram bot token from environment")
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
    else:
        # Try to get token from the first active client
        try:
            from db.client_crud import get_all_active_clients
            clients = await get_all_active_clients()

            for client in clients:
                if client.telegram_bot_token:
                    logger.info(f"Using Telegram bot token from client: {client.client_name}")
                    bot = Bot(token=client.telegram_bot_token)
                    break

            if not bot:
                logger.warning("No Telegram bot token found in environment or database")
                return

        except Exception as e:
            logger.error(f"Error getting client bot token: {e}")
            return

    try:
        await bot.delete_webhook(drop_pending_updates=True)

        dp = Dispatcher()
        dp.message.register(turn_on, Command(commands="turn_on"))
        dp.message.register(turn_off, Command(commands="turn_off"))

        logger.info("Admin bot started!")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error in admin bot: {e}")
    finally:
        if bot:
            await bot.session.close()