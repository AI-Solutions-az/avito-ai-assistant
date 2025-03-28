from db.db_config import SessionLocal
from db.models import Messages
from app.services.logs import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
import datetime

# Create
async def create_message(chat_id, author_id, from_assistant=False, message=None):
    logger.info(f"[DB] Создание сообщения в чате {chat_id}, от {author_id}")
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
            logger.info(f"[DB] Сообщение создано в чате {chat_id}, от {author_id}")
            return new_message
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при добавлении сообщения: {e}")
            await session.rollback()

# Read
async def get_latest_message_by_chat_id(chat_id):
    logger.info(f"[DB] Получение последнего сообщения из БД для чата {chat_id}")
    async with SessionLocal() as session:
        try:
            result = await session.execute(
                select(Messages.message)
                .filter(Messages.chat_id == chat_id)
                .order_by(Messages.created_at.desc())  # Сортировка по убыванию времени
            )
            latest_message = result.scalars().first()  # Получаем самое позднее сообщение
            logger.info(f"[DB] Последнее сообщение для чата {chat_id} получено из БД. Сообщение: {latest_message}")
            return latest_message
        except SQLAlchemyError as e:
            logger.error(f"[DB] Ошибка при получении сообщения: {e} - {getattr(e, 'orig', 'Нет доп. информации')}")
            return None

# Update
async def update_message(message_id, chat_id=None, author_id=None, from_assistant=None, message=None):
    async with SessionLocal() as session:
        try:
            message_record = await session.get(Messages, message_id)  # Загружаем объект в сессию
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

                await session.merge(message_record)  # Обновляем объект в сессии
                await session.commit()
            return message_record
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении сообщения: {e} - {getattr(e, 'orig', 'Нет доп. информации')}")
            await session.rollback()