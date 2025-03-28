from sqlalchemy.ext.declarative import declarative_base
from app.config import DATABASE_URL
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

# Создаем асинхронный движок
engine = create_async_engine(DATABASE_URL, future=True, echo=False)

# Создаем фабрику сессий
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)