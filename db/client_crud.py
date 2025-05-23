# db/client_crud.py

import datetime
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
from db.db_config import SessionLocal
from db.models import Clients
from app.services.logs import logger
from cryptography.fernet import Fernet
import base64
import os


# Simple encryption for storing credentials securely
def get_encryption_key():
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        # Generate a key and save it to env file for production
        key = Fernet.generate_key().decode()
        logger.warning(f"Generated new encryption key: {key}")
        logger.warning("Please add this to your environment variables as ENCRYPTION_KEY")
    return key.encode()


def encrypt_credential(credential: str) -> str:
    f = Fernet(get_encryption_key())
    return f.encrypt(credential.encode()).decode()


def decrypt_credential(encrypted_credential: str) -> str:
    f = Fernet(get_encryption_key())
    return f.decrypt(encrypted_credential.encode()).decode()


# Create new client
async def create_client(client_name: str, avito_client_id: str, avito_client_secret: str,
                        openai_api_key: str = None, openai_assistant_id: str = None,
                        telegram_bot_token: str = None, telegram_chat_id: str = None, telegram_thread_id: int = None,
                        google_api_key: str = None, google_spreadsheet_id: str = None, google_range: str = None,
                        warehouse_sheet_name: str = None, knowledge_base_sheet_name: str = None):
    async with SessionLocal() as session:
        try:
            # Encrypt sensitive data
            encrypted_secret = encrypt_credential(avito_client_secret)
            encrypted_openai_key = encrypt_credential(openai_api_key) if openai_api_key else None
            encrypted_telegram_token = encrypt_credential(telegram_bot_token) if telegram_bot_token else None
            encrypted_google_key = encrypt_credential(google_api_key) if google_api_key else None

            new_client = Clients(
                client_name=client_name,
                avito_client_id=avito_client_id,
                avito_client_secret=encrypted_secret,
                openai_api_key=encrypted_openai_key,
                openai_assistant_id=openai_assistant_id,
                telegram_bot_token=encrypted_telegram_token,
                telegram_chat_id=telegram_chat_id,
                telegram_thread_id=telegram_thread_id,
                google_api_key=encrypted_google_key,
                google_spreadsheet_id=google_spreadsheet_id,
                google_range=google_range,
                warehouse_sheet_name=warehouse_sheet_name,
                knowledge_base_sheet_name=knowledge_base_sheet_name,
                is_active=True,
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now()
            )
            session.add(new_client)
            await session.commit()
            logger.info(f"Client {client_name} created successfully")
            return new_client
        except SQLAlchemyError as e:
            logger.error(f"Error creating client: {e}")
            await session.rollback()
            return None


# Get client by Avito client ID
async def get_client_by_avito_id(avito_client_id: str):
    async with SessionLocal() as session:
        try:
            result = await session.execute(
                select(Clients).filter_by(avito_client_id=avito_client_id, is_active=True)
            )
            client = result.scalar_one_or_none()
            if client:
                # Decrypt the sensitive fields before returning
                client.avito_client_secret = decrypt_credential(client.avito_client_secret)
                if client.openai_api_key:
                    client.openai_api_key = decrypt_credential(client.openai_api_key)
                if client.telegram_bot_token:
                    client.telegram_bot_token = decrypt_credential(client.telegram_bot_token)
                if client.google_api_key:
                    client.google_api_key = decrypt_credential(client.google_api_key)
            return client
        except SQLAlchemyError as e:
            logger.error(f"Error getting client: {e}")
            return None


# Get all active clients
async def get_all_active_clients():
    async with SessionLocal() as session:
        try:
            result = await session.execute(
                select(Clients).filter_by(is_active=True)
            )
            clients = result.scalars().all()
            # Decrypt secrets for all clients
            for client in clients:
                client.avito_client_secret = decrypt_credential(client.avito_client_secret)
                if client.openai_api_key:
                    client.openai_api_key = decrypt_credential(client.openai_api_key)
                if client.telegram_bot_token:
                    client.telegram_bot_token = decrypt_credential(client.telegram_bot_token)
                if client.google_api_key:
                    client.google_api_key = decrypt_credential(client.google_api_key)
            return clients
        except SQLAlchemyError as e:
            logger.error(f"Error getting clients: {e}")
            return []


# Update client
async def update_client(client_id: int, **kwargs):
    async with SessionLocal() as session:
        try:
            client = await session.get(Clients, client_id)
            if client:
                for key, value in kwargs.items():
                    if value is not None:
                        # Encrypt sensitive fields
                        if key in ['avito_client_secret', 'openai_api_key', 'telegram_bot_token', 'google_api_key']:
                            value = encrypt_credential(value)
                        if hasattr(client, key):
                            setattr(client, key, value)
                client.updated_at = datetime.datetime.now()
                await session.commit()
            return client
        except SQLAlchemyError as e:
            logger.error(f"Error updating client: {e}")
            await session.rollback()
            return None


# Deactivate client (soft delete)
async def deactivate_client(client_id: int):
    return await update_client(client_id, is_active=False)