import asyncio
import datetime
from sqlalchemy.exc import SQLAlchemyError
from db.models import Chat
from db.db_config import SessionLocal
from sqlalchemy.future import select
from app.services.logs import logger


async def create_chat(chat_id, thread_id, client_id, user_id, chat_url, under_assistant=True, thread_id_openai=None):
    logger.info(f"[DB] Создание чата {chat_id}")
    async with SessionLocal() as session:
        try:
            new_chat = Chat(
                chat_id=str(chat_id),
                thread_id=thread_id,  # Telegram thread ID
                thread_id_openai=thread_id_openai,  # OpenAI thread ID
                client_id=str(client_id),
                user_id=str(user_id),
                chat_url=chat_url,
                under_assistant=under_assistant,
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now()
            )
            session.add(new_chat)
            await session.commit()
            logger.info(f"[DB] Чат {chat_id} создан")
            return new_chat
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при добавлении чата в БД: {e}")
            await session.rollback()


# Read
async def get_chat_by_id(chat_id):
    logger.info(f"[DB] Получение информации по чату {chat_id}")
    async with SessionLocal() as session:
        try:
            result = await session.execute(select(Chat).filter_by(chat_id=chat_id))
            chat = result.scalar_one_or_none()
            logger.info(f"[DB] Информация по чату {chat_id} получена")
            return chat
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении чата: {e}")
            return None


async def update_chat(chat_id, thread_id=None, thread_id_openai=None, client_id=None, user_id=None, under_assistant=None, chat_url=None):
    logger.info(f"Изменение чата {chat_id}")
    async with SessionLocal() as session:
        try:
            chat = await session.get(Chat, chat_id)  # Получаем объект внутри сессии
            if chat:
                if thread_id is not None:
                    chat.thread_id = thread_id  # Telegram thread ID
                if thread_id_openai is not None:
                    chat.thread_id_openai = thread_id_openai  # OpenAI thread ID
                if client_id is not None:
                    chat.client_id = client_id
                if user_id is not None:
                    chat.user_id = user_id
                if chat_url is not None:
                    chat.chat_url = chat_url
                if under_assistant is not None:
                    chat.under_assistant = under_assistant
                chat.updated_at = datetime.datetime.now()

                await session.merge(chat)  # Обновляем объект в сессии
                await session.commit()
            return chat
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении чата: {e} - {getattr(e, 'orig', 'Нет доп. информации')}")
            await session.rollback()


# Delete
async def delete_chat(chat_id):
    async with SessionLocal() as session:
        try:
            chat = await get_chat_by_id(chat_id)
            if chat:
                await session.delete(chat)
                await session.commit()
            return chat
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при удалении чата: {e}")
            await session.rollback()


async def update_chat_by_thread(thread_id: int, under_assistant: bool) -> None:
    """Обновляет информацию о чате в БД по thread_id (Telegram thread ID)."""
    async with SessionLocal() as session:
        try:
            result = await session.execute(select(Chat).where(Chat.thread_id == thread_id).limit(1))
            chat = result.scalars().first()

            if chat:
                chat.under_assistant = under_assistant
                chat.updated_at = datetime.datetime.now()

                await session.commit()
                logger.info(f"Чат {thread_id} обновлен: under_assistant={under_assistant}")
            else:
                logger.warning(f"Чат с thread_id={thread_id} не найден в базе данных")

        except SQLAlchemyError as e:
            logger.error(f"Ошибка обновления чата {thread_id}: {e}")
            await session.rollback()