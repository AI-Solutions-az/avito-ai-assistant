# db/chat_crud.py - Updated version

import asyncio
import datetime
from sqlalchemy.exc import SQLAlchemyError
from db.models import Chat
from db.db_config import SessionLocal
from sqlalchemy.future import select
from app.services.logs import logger

# UPDATED: Added client_db_id parameter
async def create_chat(chat_id, thread_id, client_id, user_id, chat_url, under_assistant=True, 
                     thread_id_openai=None, client_db_id=None):
    logger.info(f"[DB] Creating chat {chat_id} for client DB ID {client_db_id}")
    async with SessionLocal() as session:
        try:
            new_chat = Chat(
                chat_id=str(chat_id),
                client_db_id=client_db_id,  # NEW: Store reference to clients table
                thread_id=thread_id,  # Telegram thread ID
                thread_id_openai=thread_id_openai,  # OpenAI thread ID
                client_id=str(client_id),  # Avito client ID (author_id from webhook)
                user_id=str(user_id),  # Avito user ID
                chat_url=chat_url,
                under_assistant=under_assistant,
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now()
            )
            session.add(new_chat)
            await session.commit()
            logger.info(f"[DB] Chat {chat_id} created for client DB ID {client_db_id}")
            return new_chat
        except SQLAlchemyError as e:
            logger.error(f"Error creating chat in DB: {e}")
            await session.rollback()

# Read - unchanged
async def get_chat_by_id(chat_id):
    logger.info(f"[DB] Getting chat info for {chat_id}")
    async with SessionLocal() as session:
        try:
            result = await session.execute(select(Chat).filter_by(chat_id=chat_id))
            chat = result.scalar_one_or_none()
            logger.info(f"[DB] Chat info for {chat_id} retrieved")
            return chat
        except SQLAlchemyError as e:
            logger.error(f"Error getting chat: {e}")
            return None

# UPDATED: Added client_db_id parameter
async def update_chat(chat_id, thread_id=None, thread_id_openai=None, client_id=None, 
                     user_id=None, under_assistant=None, chat_url=None, client_db_id=None):
    logger.info(f"Updating chat {chat_id}")
    async with SessionLocal() as session:
        try:
            chat = await session.get(Chat, chat_id)
            if chat:
                if thread_id is not None:
                    chat.thread_id = thread_id
                if thread_id_openai is not None:
                    chat.thread_id_openai = thread_id_openai
                if client_id is not None:
                    chat.client_id = client_id
                if user_id is not None:
                    chat.user_id = user_id
                if chat_url is not None:
                    chat.chat_url = chat_url
                if under_assistant is not None:
                    chat.under_assistant = under_assistant
                if client_db_id is not None:  # NEW: Allow updating client reference
                    chat.client_db_id = client_db_id
                chat.updated_at = datetime.datetime.now()

                await session.merge(chat)
                await session.commit()
            return chat
        except SQLAlchemyError as e:
            logger.error(f"Error updating chat: {e} - {getattr(e, 'orig', 'No additional info')}")
            await session.rollback()

# Delete - unchanged
async def delete_chat(chat_id):
    async with SessionLocal() as session:
        try:
            chat = await get_chat_by_id(chat_id)
            if chat:
                await session.delete(chat)
                await session.commit()
            return chat
        except SQLAlchemyError as e:
            logger.error(f"Error deleting chat: {e}")
            await session.rollback()

# Update by thread - unchanged  
async def update_chat_by_thread(thread_id: int, under_assistant: bool) -> None:
    """Update chat info in DB by thread_id (Telegram thread ID)."""
    async with SessionLocal() as session:
        try:
            result = await session.execute(select(Chat).where(Chat.thread_id == thread_id).limit(1))
            chat = result.scalars().first()

            if chat:
                chat.under_assistant = under_assistant
                chat.updated_at = datetime.datetime.now()

                await session.commit()
                logger.info(f"Chat {thread_id} updated: under_assistant={under_assistant}")
            else:
                logger.warning(f"Chat with thread_id={thread_id} not found in database")

        except SQLAlchemyError as e:
            logger.error(f"Error updating chat {thread_id}: {e}")
            await session.rollback()

# NEW: Get chat by client DB ID
async def get_chats_by_client_db_id(client_db_id: int):
    """Get all chats for a specific client"""
    async with SessionLocal() as session:
        try:
            result = await session.execute(select(Chat).filter_by(client_db_id=client_db_id))
            chats = result.scalars().all()
            return chats
        except SQLAlchemyError as e:
            logger.error(f"Error getting chats for client {client_db_id}: {e}")
            return []