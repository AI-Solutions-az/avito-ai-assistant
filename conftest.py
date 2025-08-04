import asyncio
import pytest
from sqlalchemy import text
import pytest_asyncio
from db.db_config import engine, SessionLocal
from unittest.mock import patch, AsyncMock, MagicMock


# КРИТИЧЕСКИ ВАЖНО: Управляем event loop для корректной работы с asyncpg
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def clean_db():
    """Очищает БД перед и после каждого теста"""
    # Очищаем БД перед тестом
    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE TABLE assistant.messages, assistant.chat RESTART IDENTITY CASCADE;")
        )

    yield

    # Очищаем БД после теста
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("TRUNCATE TABLE assistant.messages, assistant.chat RESTART IDENTITY CASCADE;")
            )
    except Exception:
        pass

    # Важно: закрываем все соединения после теста
    await engine.dispose()


class DummyBot:
    """Заглушка для Telegram бота"""

    def __init__(self):
        self.session = MagicMock()

    async def send_message(self, *args, **kwargs):
        return MagicMock()

    async def create_forum_topic(self, *args, **kwargs):
        class DummyResponse:
            message_thread_id = 123

        return DummyResponse()

    async def delete_webhook(self, *args, **kwargs):
        return True


@pytest.fixture(scope="function")
def all_mocks(clean_db):  # Добавляем clean_db как зависимость
    """Создает все необходимые моки для тестов"""
    dummy_bot = DummyBot()

    with patch('app.routes.chat.message_queues', {}), \
            patch('app.routes.chat.processing_tasks', {}), \
            patch('app.services.telegram_bot.bot', dummy_bot), \
            patch('app.services.telegram_notifier.bot', dummy_bot), \
            patch('app.routes.chat.message_collector', new_callable=AsyncMock) as mock_collector, \
            patch("app.routes.chat.process_message", new_callable=AsyncMock) as mock_process, \
            patch("app.routes.chat.send_alert", new_callable=AsyncMock) as mock_alert, \
            patch("app.routes.chat.send_message", new_callable=AsyncMock) as mock_send, \
            patch("app.routes.chat.create_telegram_forum_topic", new_callable=AsyncMock) as mock_forum, \
            patch("app.routes.chat.get_ad", new_callable=AsyncMock) as mock_ad, \
            patch("app.routes.chat.get_user_info", new_callable=AsyncMock) as mock_user:
        # Устанавливаем значения по умолчанию
        # ВАЖНО: НЕ устанавливаем side_effect для collector по умолчанию,
        # чтобы каждый тест мог настроить свою логику
        mock_collector.return_value = None
        mock_process.return_value = "Ответ от GPT"
        mock_alert.return_value = None
        mock_send.return_value = None
        mock_forum.return_value = 123
        mock_ad.return_value = "https://fake_ad_url"
        mock_user.return_value = ("Test User", "https://fake_user_url")

        yield {
            'collector': mock_collector,
            'process': mock_process,
            'alert': mock_alert,
            'send': mock_send,
            'forum': mock_forum,
            'ad': mock_ad,
            'user': mock_user,
            'bot': dummy_bot
        }

# Добавляем фикстуру для изоляции тестов
@pytest.fixture(autouse=True)
def isolate_tests():
    """Изолирует тесты друг от друга"""
    yield
    # Очищаем любые оставшиеся моки/патчи
    try:
        patch.stopall()
    except Exception:
        pass


# Настройка pytest-asyncio
pytest_plugins = ('pytest_asyncio',)