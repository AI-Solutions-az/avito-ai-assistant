from db.db_config import SessionLocal
from db.models import Messages
from app.services.logs import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
import datetime

# Create
async def create_message(chat_id, author_id, from_assistant=False, message=None):
    async with SessionLocal() as session:
        try:
            new_message = Messages(
                chat_id=str(chat_id),
                author_id=str(author_id),
                from_assistant=from_assistant,
                message=message,
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now()
            )
            session.add(new_message)
            await session.commit()
            return new_message
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при добавлении сообщения: {e}")
            await session.rollback()

# Read
async def get_message_by_id(message_id):
    async with SessionLocal() as session:
        try:
            result = await session.execute(select(Messages).filter_by(id=message_id))
            message = result.scalar_one_or_none()
            return message
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении сообщения: {e}")
            return None

# Update
async def update_message(message_id, chat_id=None, author_id=None, from_assistant=None, message=None):
    async with SessionLocal() as session:
        try:
            message_record = await get_message_by_id(message_id)
            if message_record:
                if chat_id is not None:
                    message_record.chat_id = chat_id
                if author_id is not None:
                    message_record.author_id = author_id
                if from_assistant is not None:
                    message_record.from_assistant = from_assistant
                if message is not None:
                    message_record.message = message
                message_record.updated_at = datetime.datetime.now()
                await session.commit()
            return message_record
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении сообщения: {e}")
            await session.rollback()

# Delete
async def delete_message(message_id):
    async with SessionLocal() as session:
        try:
            message_record = await get_message_by_id(message_id)
            if message_record:
                await session.delete(message_record)
                await session.commit()
            return message_record
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при удалении сообщения: {e}")
            await session.rollback()