from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
import datetime
from db.db_config import SessionLocal
from db.models import Returns
from app.services.logs import logger

# Create
async def create_return(chat_id, client_id, client_name, reason, good_url):
    async with SessionLocal() as session:
        try:
            new_return = Returns(
                chat_id=chat_id,
                client_id=client_id,
                client_name=client_name,
                reason=reason,
                good_url=good_url,
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now()
            )
            session.add(new_return)
            await session.commit()
            return new_return
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при добавлении возврата: {e}")
            await session.rollback()

# Read
async def get_return_by_id(return_id):
    async with SessionLocal() as session:
        try:
            result = await session.execute(select(Returns).filter_by(id=return_id))
            return_record = result.scalar_one_or_none()
            return return_record
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении возврата: {e}")
            return None

# Update
async def update_return(return_id, chat_id=None, client_id=None, client_name=None, reason=None, good_url=None):
    async with SessionLocal() as session:
        try:
            return_record = await get_return_by_id(return_id)
            if return_record:
                if chat_id is not None:
                    return_record.chat_id = chat_id
                if client_id is not None:
                    return_record.client_id = client_id
                if client_name is not None:
                    return_record.client_name = client_name
                if reason is not None:
                    return_record.reason = reason
                if good_url is not None:
                    return_record.good_url = good_url
                return_record.updated_at = datetime.datetime.now()
                await session.commit()
            return return_record
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении возврата: {e}")
            await session.rollback()

# Delete
async def delete_return(return_id):
    async with SessionLocal() as session:
        try:
            return_record = await get_return_by_id(return_id)
            if return_record:
                await session.delete(return_record)
                await session.commit()
            return return_record
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при удалении возврата: {e}")
            await session.rollback()