import datetime
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from db.db_config import SessionLocal
from db.models import Escalations
from app.services.logs import logger

# Create
async def create_escalation(chat_id, client_id, client_name, chat_url, reason):
    async with SessionLocal() as session:
        try:
            new_escalation = Escalations(
                chat_id=str(chat_id),
                client_id=str(client_id),
                client_name=client_name,
                chat_url=chat_url,
                reason=reason,
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now()
            )
            session.add(new_escalation)
            await session.commit()
            return new_escalation
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при добавлении эскалации: {e}")
            await session.rollback()

# Read
async def get_escalation_by_id(escalation_id):
    async with SessionLocal() as session:
        try:
            result = await session.execute(select(Escalations).filter_by(id=escalation_id))
            escalation = result.scalar_one_or_none()
            return escalation
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении эскалации: {e}")
            return None

# Update escalation
async def update_escalation(escalation_id, chat_id=None, client_id=None, client_name=None, chat_url=None, reason=None):
    async with SessionLocal() as session:
        try:
            escalation = await session.get(Escalations, escalation_id)  # Загружаем объект внутри сессии
            if escalation:
                if chat_id is not None:
                    escalation.chat_id = chat_id
                if client_id is not None:
                    escalation.client_id = client_id
                if client_name is not None:
                    escalation.client_name = client_name
                if chat_url is not None:
                    escalation.chat_url = chat_url
                if reason is not None:
                    escalation.reason = reason
                escalation.updated_at = datetime.datetime.now()

                await session.merge(escalation)  # Обновляем объект в сессии
                await session.commit()
            return escalation
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении эскалации: {e} - {getattr(e, 'orig', 'Нет доп. информации')}")
            await session.rollback()

# Delete
async def delete_escalation(escalation_id):
    async with SessionLocal() as session:
        try:
            escalation = await get_escalation_by_id(escalation_id)
            if escalation:
                await session.delete(escalation)
                await session.commit()
            return escalation
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при удалении эскалации: {e}")
            await session.rollback()