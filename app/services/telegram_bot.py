from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from app.config import TELEGRAM_BOT_TOKEN
from app.services.logs import logger
from db.chat_crud import update_chat_by_thread

bot = Bot(token=TELEGRAM_BOT_TOKEN)

async def turn_on(message: Message) -> None:
    """Команда /turn_on — подключает бота к диалогу."""
    thread_id = message.message_thread_id
    await update_chat_by_thread(thread_id, True)
    await message.answer("Бот подключен к диалогу")

async def turn_off(message: Message) -> None:
    """Команда /turn_off — отключает бота от диалога."""
    thread_id = message.message_thread_id
    await update_chat_by_thread(thread_id, False)
    await message.answer("Бот отключен от диалога")

async def start_bot() -> None:
    """Запуск бота."""
    await bot.delete_webhook(drop_pending_updates=True)

    dp = Dispatcher()
    dp.message.register(turn_on, Command(commands="turn_on"))
    dp.message.register(turn_off, Command(commands="turn_off"))

    try:
        logger.info("Бот запущен!")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()