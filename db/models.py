from sqlalchemy import Column, String, Boolean, Integer, DateTime
from db.db_config import Base

class Chat(Base):
    __tablename__ = 'chat'
    __table_args__ = {'schema': 'assistant'}

    chat_id = Column(String, primary_key=True)
    thread_id = Column(Integer, default=0)
    client_id = Column(String) # Идентификатор клиента
    user_id = Column(String) # Идентификатор владельца аккаунта
    chat_url = Column(String)
    under_assistant = Column(Boolean, default=True)
    updated_at = Column(DateTime)
    created_at = Column(DateTime)


class Messages(Base):
    __tablename__ = 'messages'
    __table_args__ = {'schema': 'assistant'}

    id = Column(Integer, primary_key=True)
    chat_id = Column(String)
    author_id = Column(String)
    from_assistant = Column(Boolean, default=False) # True значит от ассистента, False либо от оператора либо от клиента
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