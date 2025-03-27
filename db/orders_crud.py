from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
import datetime
from db.db_config import SessionLocal
from db.models import Orders
from app.services.logs import logger

# Create
async def create_order(chat_id, client_id, client_name, color, size, good_url, good_name):
    async with SessionLocal() as session:
        try:
            new_order = Orders(
                chat_id=chat_id,
                client_id=client_id,
                client_name=client_name,
                color=color,
                size=size,
                good_url=good_url,
                good_name=good_name,
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now()
            )
            session.add(new_order)
            await session.commit()
            return new_order
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при добавлении заказа: {e}")
            await session.rollback()

# Read
async def get_order_by_id(order_id):
    async with SessionLocal() as session:
        try:
            result = await session.execute(select(Orders).filter_by(id=order_id))
            order = result.scalar_one_or_none()
            return order
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении заказа: {e}")
            return None

# Update
async def update_order(order_id, chat_id=None, client_id=None, client_name=None, color=None, size=None, good_url=None):
    async with SessionLocal() as session:
        try:
            order = await get_order_by_id(order_id)
            if order:
                if chat_id is not None:
                    order.chat_id = chat_id
                if client_id is not None:
                    order.client_id = client_id
                if client_name is not None:
                    order.client_name = client_name
                if color is not None:
                    order.color = color
                if size is not None:
                    order.size = size
                if good_url is not None:
                    order.good_url = good_url
                order.updated_at = datetime.datetime.now()
                await session.commit()
            return order
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении заказа: {e}")
            await session.rollback()

# Delete
async def delete_order(order_id):
    async with SessionLocal() as session:
        try:
            order = await get_order_by_id(order_id)
            if order:
                await session.delete(order)
                await session.commit()
            return order
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при удалении заказа: {e}")
            await session.rollback()