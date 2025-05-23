# db/models.py - Updated version

from sqlalchemy import Column, String, Boolean, Integer, DateTime
from db.db_config import Base


# NEW: Clients table for multi-client support
class Clients(Base):
    __tablename__ = 'clients'
    __table_args__ = {'schema': 'assistant'}

    id = Column(Integer, primary_key=True)
    client_name = Column(String, nullable=False)

    # Avito API credentials
    avito_client_id = Column(String, nullable=False, unique=True)
    avito_client_secret = Column(String, nullable=False)

    # OpenAI configuration
    openai_api_key = Column(String, nullable=True)
    openai_assistant_id = Column(String, nullable=True)

    # Telegram configuration
    telegram_bot_token = Column(String, nullable=True)
    telegram_chat_id = Column(String, nullable=True)
    telegram_thread_id = Column(Integer, nullable=True)

    # Google Sheets configuration
    google_api_key = Column(String, nullable=True)
    google_spreadsheet_id = Column(String, nullable=True)
    google_range = Column(String, nullable=True)
    warehouse_sheet_name = Column(String, nullable=True)
    knowledge_base_sheet_name = Column(String, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


# UPDATED: Chat table with client reference
class Chat(Base):
    __tablename__ = 'chat'
    __table_args__ = {'schema': 'assistant'}

    chat_id = Column(String, primary_key=True)
    client_db_id = Column(Integer)  # NEW: Reference to Clients table
    thread_id = Column(Integer, default=0)  # Telegram thread ID
    thread_id_openai = Column(String)  # OpenAI thread ID
    client_id = Column(String)  # Avito client ID (author_id from webhook)
    user_id = Column(String)  # Avito user ID
    chat_url = Column(String)
    under_assistant = Column(Boolean, default=True)
    updated_at = Column(DateTime)
    created_at = Column(DateTime)


# Existing models remain the same
class Messages(Base):
    __tablename__ = 'messages'
    __table_args__ = {'schema': 'assistant'}

    id = Column(Integer, primary_key=True)
    chat_id = Column(String)
    author_id = Column(String)
    from_assistant = Column(Boolean, default=False)
    message = Column(String)
    updated_at = Column(DateTime)
    created_at = Column(DateTime)


class Orders(Base):
    __tablename__ = 'orders'
    __table_args__ = {'schema': 'assistant'}

    id = Column(Integer, primary_key=True)
    chat_id = Column(String)
    client_id = Column(String)
    client_name = Column(String)
    color = Column(String)
    size = Column(String)
    good_name = Column(String)
    good_url = Column(String)
    updated_at = Column(DateTime)
    created_at = Column(DateTime)


class Returns(Base):
    __tablename__ = 'returns'
    __table_args__ = {'schema': 'assistant'}

    id = Column(Integer, primary_key=True)
    chat_id = Column(String)
    client_id = Column(String)
    client_name = Column(String)
    reason = Column(String)
    good_url = Column(String)
    updated_at = Column(DateTime)
    created_at = Column(DateTime)


class Escalations(Base):
    __tablename__ = 'escalation'
    __table_args__ = {'schema': 'assistant'}

    id = Column(Integer, primary_key=True)
    chat_id = Column(String)
    client_id = Column(String)
    client_name = Column(String)
    chat_url = Column(String)
    reason = Column(String)
    updated_at = Column(DateTime)
    created_at = Column(DateTime)