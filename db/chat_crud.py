import asyncio
import datetime
from sqlalchemy.exc import SQLAlchemyError
from db.models import Chat
from db.db_config import SessionLocal
from sqlalchemy.future import select
from app.services.logs import logger

async def create_chat(chat_id, thread_id, client_id, user_id, chat_url, under_assistant=True):
    async with SessionLocal() as session:
        try:
            new_chat = Chat(
                chat_id=chat_id,
                thread_id=thread_id,
                client_id=client_id,
                user_id=user_id,
                chat_url=chat_url,
                under_assistant=under_assistant,
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now()
            )
            session.add(new_chat)
            await session.commit()
            return new_chat
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при добавлении чата в БД: {e}")
            await session.rollback()

# Read
async def get_chat_by_id(chat_id):
    async with SessionLocal() as session:
        try:
            result = await session.execute(select(Chat).filter_by(chat_id=chat_id))
            chat = result.scalar_one_or_none()
            return chat
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении чата: {e}")
            return None

# Update
async def update_chat(chat_id, thread_id=None, client_id=None, user_id=None, under_assistant=None, chat_url=None):
    async with SessionLocal() as session:
        try:
            chat = await get_chat_by_id(chat_id)
            if chat:
                if thread_id is not None:
                    chat.thread_id = thread_id
                if client_id is not None:
                    chat.client_id = client_id
                if user_id is not None:
                    chat.user_id = user_id
                if chat_url is not None:
                    chat.chat_url = chat_url
                if under_assistant is not None:
                    chat.under_assistant = under_assistant
                chat.updated_at = datetime.datetime.now()
                await session.commit()
            return chat
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении чата: {e}")
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

#asyncio.run(create_chat('123',123,'1243','4324d','fdwf'))
print(asyncio.run(get_chat_by_id('123')).chat_url)