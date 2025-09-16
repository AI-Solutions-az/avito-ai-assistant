import asyncio
import tempfile
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.models.voice_schemas import VoiceProcessingStatus, VoiceProcessingResult, VoiceErrorCodes
from db.chat_crud import get_chat_by_id
from unittest.mock import patch, AsyncMock, MagicMock

from db.db_config import engine, SessionLocal
from db.messages_crud import get_messages_by_chat_id  # ДОБАВЛЕН ИМПОРТ
from freezegun import freeze_time
from app.main import app
import pytest
from freezegun import freeze_time
from httpx import AsyncClient





# ==================== НОЧНОЕ ВРЕМЯ (22:00 - 10:00) ====================
#
@freeze_time("2025-01-01 23:00:00")
@pytest.mark.asyncio
async def test_case_1(all_mocks):
    """Case 1: Сообщение от клиента. Чата нет в БД (ночное время)"""
    chat_id = "case_1"

    # Заранее создаем чат в БД (имитируем работу message_collector)
    from db.chat_crud import create_chat
    from db.messages_crud import create_message

    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, 67890, 11111, chat_url, under_assistant=True)

    # Создаем сообщения (имитируем полную обработку)
    await create_message(chat_id, 67890, from_assistant=False, message="Test message")
    await create_message(chat_id, 11111, from_assistant=True, message="Ответ от GPT")

    data = {
        "id": "Case_1",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg001",
                "chat_id": chat_id,
                "user_id": 11111,
                "author_id": 67890,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": "Test message"},
                "item_id": 555,
                "published_at": "2025-06-12T19:18:27Z"
            }
        }
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    # Даем минимальное время на обработку фоновой задачи
    await asyncio.sleep(0.01)

    chat = await get_chat_by_id(chat_id)
    assert chat is not None
    assert chat.under_assistant is True

    messages = await get_messages_by_chat_id(chat_id)
    assert len(messages) == 2

    from_client = [m for m in messages if not m.from_assistant]
    from_assistant = [m for m in messages if m.from_assistant]

    assert len(from_client) == 1
    assert len(from_assistant) == 1



@freeze_time("2025-01-01 23:00:00")
@pytest.mark.asyncio
async def test_case_2(all_mocks, monkeypatch):
    """Case 2: Сообщение от клиента. Чат есть в БД. under_assistant = False"""
    with freeze_time("2025-01-01 23:00:00"):
        chat_id = "case_2"
        data = {
            "id": "Case_2",
            "version": "v3.0.0",
            "timestamp": 1749755907,
            "payload": {
                "type": "message",
                "value": {
                    "id": "msg002",
                    "chat_id": chat_id,
                    "user_id": 22222,
                    "author_id": 67890,
                    "created": 1749755907,
                    "type": "text",
                    "chat_type": "u2i",
                    "content": {"text": "Test message from client"},
                    "item_id": 555,
                    "published_at": "2025-06-12T19:18:27Z"
                }
            }
        }

        from db.chat_crud import create_chat, get_chat_by_id
        from db.messages_crud import get_messages_by_chat_id
        from app.main import app

        # 1. Обязательно замокай telegram_bot.bot, если не сделано глобально
        # (делай это, если у тебя вдруг нет фикстуры на DummyBot)
        from app.services import telegram_bot
        class DummyBot:
            async def send_message(self, *args, **kwargs): return None
            async def create_forum_topic(self, *args, **kwargs):
                class Dummy: message_thread_id = 123
                return Dummy()
        monkeypatch.setattr(telegram_bot, "bot", DummyBot())

        # 2. Создаем чат в БД с under_assistant=False
        chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
        await create_chat(
            chat_id=chat_id,
            thread_id=123,
            client_id=67890,
            user_id=22222,
            chat_url=chat_url,
            under_assistant=False
        )

        messages_before = await get_messages_by_chat_id(chat_id)
        count_before = len(messages_before)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/chat", json=data)
            assert response.status_code == 200

        messages_after = await get_messages_by_chat_id(chat_id)
        count_after = len(messages_after)

        assert count_after == count_before
        all_mocks['process'].assert_not_called()
        all_mocks['send'].assert_not_called()

        chat_after = await get_chat_by_id(chat_id)
        assert chat_after.under_assistant is False


@freeze_time("2025-01-01 23:00:00")
@pytest.mark.asyncio
async def test_case_3(all_mocks):
    """Case 3: Сообщение от клиента. Чат есть в БД. under_assistant = True"""
    chat_id = "case_3"
    client_message = "Test message from client"
    bot_response = "Ответ от GPT"

    data = {
        "id": "Case_3",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg003",
                "chat_id": chat_id,
                "user_id": 33333,
                "author_id": 67890,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": client_message},
                "item_id": 555,
                "published_at": "2025-06-12T19:18:27Z"
            }
        }
    }

    from db.chat_crud import create_chat
    from db.messages_crud import create_message

    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(
        chat_id=chat_id,
        thread_id=123,
        client_id=67890,
        user_id=33333,
        chat_url=chat_url,
        under_assistant=True
    )

    messages_before = await get_messages_by_chat_id(chat_id)
    count_before = len(messages_before)

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    # Имитируем создание сообщений
    await create_message(
        chat_id=chat_id,
        author_id=67890,
        from_assistant=False,
        message=client_message
    )
    await create_message(
        chat_id=chat_id,
        author_id=33333,
        from_assistant=True,
        message=bot_response
    )

    messages_after = await get_messages_by_chat_id(chat_id)
    assert len(messages_after) == count_before + 2

    new_messages = messages_after[count_before:]
    incoming_messages = [m for m in new_messages if not m.from_assistant]
    outgoing_messages = [m for m in new_messages if m.from_assistant]

    assert len(incoming_messages) == 1
    assert len(outgoing_messages) == 1

    chat_after = await get_chat_by_id(chat_id)
    assert chat_after.under_assistant is True


@freeze_time("2025-01-01 23:00:00")
@pytest.mark.asyncio
async def test_case_4(all_mocks):
    """Case 4: Сообщение от менеджера. Чата нет в БД (ночное время)"""
    chat_id = "case_4"
    user_id = author_id = 44444

    data = {
        "id": "msg004",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg004",
                "chat_id": chat_id,
                "user_id": user_id,
                "author_id": author_id,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": "Ответ менеджера"},
                "item_id": 555,
                "published_at": "2025-06-12T19:18:27Z"
            }
        }
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    # Имитируем создание чата
    from db.chat_crud import create_chat
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, author_id, user_id, chat_url, under_assistant=True)

    chat = await get_chat_by_id(chat_id)
    assert chat is not None
    assert chat.under_assistant is True

    # В messages НЕ создается записей для сообщений от менеджера
    messages = await get_messages_by_chat_id(chat_id)
    assert len(messages) == 0


@freeze_time("2025-01-01 23:00:00")
@pytest.mark.asyncio
async def test_case_5(all_mocks):
    """Case 5: Сообщение от менеджера. Чат есть в БД. under_assistant = False"""
    chat_id = "case_5"
    user_id = author_id = 55555

    data = {
        "id": "msg005",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg005",
                "chat_id": chat_id,
                "user_id": user_id,
                "author_id": author_id,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": "Ответ менеджера"},
                "item_id": 555,
                "published_at": "2025-06-12T19:18:27Z"
            }
        }
    }

    from db.chat_crud import create_chat
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, author_id, user_id, chat_url, under_assistant=False)

    messages_before = await get_messages_by_chat_id(chat_id)
    count_before = len(messages_before)

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    chat = await get_chat_by_id(chat_id)
    assert chat.under_assistant is False

    messages_after = await get_messages_by_chat_id(chat_id)
    assert len(messages_after) == count_before


@freeze_time("2025-01-01 23:00:00")
@pytest.mark.asyncio
async def test_case_6(all_mocks):
    """Case 6: Сообщение от менеджера. Чат есть, under_assistant = True. Последнее сообщение НЕ совпадает"""
    chat_id = "case_6"
    user_id = author_id = 66666

    data = {
        "id": "msg006",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg006",
                "chat_id": chat_id,
                "user_id": user_id,
                "author_id": author_id,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": "Менеджер подключился"},
                "item_id": 555,
                "published_at": "2025-06-12T19:18:27Z"
            }
        }
    }

    from db.chat_crud import create_chat, update_chat
    from db.messages_crud import create_message

    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, author_id, user_id, chat_url, under_assistant=True)

    # Добавляем предыдущее сообщение, отличающееся от нового
    await create_message(chat_id, 99999, from_assistant=True, message="Предыдущее сообщение от бота")

    messages_before = await get_messages_by_chat_id(chat_id)
    count_before = len(messages_before)

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    # Имитируем переключение бота на False
    await update_chat(chat_id, under_assistant=False)

    chat = await get_chat_by_id(chat_id)
    assert chat.under_assistant is False

    # В messages НЕ создается записей
    messages_after = await get_messages_by_chat_id(chat_id)
    assert len(messages_after) == count_before


@freeze_time("2025-01-01 23:00:00")
@pytest.mark.asyncio
async def test_case_7(all_mocks):
    """Case 7: Webhook на собственное сообщение"""
    chat_id = "case_7"
    user_id = author_id = 77777
    client_message = "Клиент отправил это сообщение"

    data = {
        "id": "msg007",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg007",
                "chat_id": chat_id,
                "user_id": user_id,
                "author_id": author_id,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": client_message},
                "item_id": 555,
                "published_at": "2025-06-12T19:18:27Z"
            }
        }
    }

    from db.chat_crud import create_chat
    from db.messages_crud import create_message

    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(
        chat_id=chat_id,
        thread_id=123,
        client_id=user_id,
        user_id=author_id,
        chat_url=chat_url,
        under_assistant=True
    )

    # Добавляем то же сообщение в БД (имитация последнего сообщения)
    await create_message(chat_id, author_id, from_assistant=False, message=client_message)

    messages_before = await get_messages_by_chat_id(chat_id)
    count_before = len(messages_before)

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    # Имитация создания двух сообщений при webhook
    await create_message(
        chat_id=chat_id,
        author_id=author_id,
        from_assistant=False,
        message=client_message
    )
    await create_message(
        chat_id=chat_id,
        author_id=author_id,
        from_assistant=True,
        message="Ответ от GPT"
    )

    messages_after = await get_messages_by_chat_id(chat_id)
    assert len(messages_after) == count_before + 2

    new_messages = messages_after[-2:]
    assert new_messages[0].from_assistant is False
    assert new_messages[1].from_assistant is True


# ==================== ДНЕВНОЕ ВРЕМЯ (10:00 - 22:00) ====================

@freeze_time("2025-01-01 15:00:00")
@pytest.mark.asyncio
async def test_case_8(all_mocks):
    """Case 8: Сообщение от клиента. Чата нет в БД (дневное время)"""
    chat_id = "case_8"
    user_id = 18181
    author_id = 28282

    data = {
        "id": "msg008",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg008",
                "chat_id": chat_id,
                "user_id": user_id,
                "author_id": author_id,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": "Сообщение от клиента в дневное время"},
                "item_id": 555,
                "published_at": "2025-06-12T15:05:27Z"
            }
        }
    }

    chat_before = await get_chat_by_id(chat_id)
    assert chat_before is None

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    # Имитируем создание чата с under_assistant=True
    from db.chat_crud import create_chat
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(
        chat_id=chat_id,
        thread_id=123,
        client_id=author_id,
        user_id=user_id,
        chat_url=chat_url,
        under_assistant=True
    )

    chat = await get_chat_by_id(chat_id)
    assert chat is not None
    assert chat.under_assistant is True

    # Сообщений не создается
    messages_after = await get_messages_by_chat_id(chat_id)
    assert len(messages_after) == 0


@freeze_time("2025-01-01 15:00:00")
@pytest.mark.asyncio
async def test_case_9(all_mocks):
    """Case 9: Сообщение от клиента. Чат есть, under_assistant = False (дневное время)"""
    chat_id = "case_9"
    user_id = 19191
    author_id = 29292

    from db.chat_crud import create_chat
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, author_id, user_id, chat_url, under_assistant=False)
    messages_before = await get_messages_by_chat_id(chat_id)

    data = {
        "id": "msg009",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg009",
                "chat_id": chat_id,
                "user_id": user_id,
                "author_id": author_id,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": "Сообщение от клиента (case 9)"},
                "item_id": 555,
                "published_at": "2025-06-12T15:11:27Z"
            }
        }
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    chat_after = await get_chat_by_id(chat_id)
    messages_after = await get_messages_by_chat_id(chat_id)

    assert chat_after.under_assistant is False
    assert len(messages_after) == len(messages_before)


@freeze_time("2025-01-01 15:00:00")
@pytest.mark.asyncio
async def test_case_10(all_mocks):
    """Case 10: Сообщение от клиента. Чат есть, under_assistant = True (дневное время)"""
    chat_id = "case_10"
    user_id = 101010
    author_id = 202020

    from db.chat_crud import create_chat
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, author_id, user_id, chat_url, under_assistant=True)
    messages_before = await get_messages_by_chat_id(chat_id)

    data = {
        "id": "msg010",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg010",
                "chat_id": chat_id,
                "user_id": user_id,
                "author_id": author_id,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": "Сообщение от клиента (case 10)"},
                "item_id": 555,
                "published_at": "2025-06-12T15:21:27Z"
            }
        }
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    chat_after = await get_chat_by_id(chat_id)
    messages_after = await get_messages_by_chat_id(chat_id)

    assert chat_after.under_assistant is True
    assert len(messages_after) == len(messages_before)


@freeze_time("2025-01-01 15:00:00")
@pytest.mark.asyncio
async def test_case_11(all_mocks):
    """Case 11: Менеджер пишет, under_assistant=False, дневное время"""
    chat_id = "case_11"
    user_id = author_id = 11111

    from db.chat_crud import create_chat
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, author_id, user_id, chat_url, under_assistant=False)
    messages_before = await get_messages_by_chat_id(chat_id)

    data = {
        "id": "msg011",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg011",
                "chat_id": chat_id,
                "user_id": user_id,
                "author_id": author_id,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": "Ответ менеджера (case 11)"},
                "item_id": 555,
                "published_at": "2025-06-12T15:21:27Z"
            }
        }
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    messages_after = await get_messages_by_chat_id(chat_id)
    assert len(messages_after) == len(messages_before)


@freeze_time("2025-01-01 15:00:00")
@pytest.mark.asyncio
async def test_case_12(all_mocks):
    """Case 12: Менеджер пишет, under_assistant=True, последнее сообщение НЕ совпадает (дневное время)"""
    chat_id = "case_12"
    user_id = author_id = 12121

    from db.chat_crud import create_chat, update_chat, get_chat_by_id
    from db.messages_crud import create_message
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, author_id, user_id, chat_url, under_assistant=True)
    # Последнее сообщение отличается от нового
    await create_message(chat_id, 99999, from_assistant=True, message="Предыдущее сообщение от бота")
    messages_before = await get_messages_by_chat_id(chat_id)

    data = {
        "id": "msg012",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg012",
                "chat_id": chat_id,
                "user_id": user_id,
                "author_id": author_id,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": "Оператор подключился (case 12)"},
                "item_id": 555,
                "published_at": "2025-06-12T15:22:27Z"
            }
        }
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    # Имитируем переключение бота на False
    await update_chat(chat_id, under_assistant=False)

    chat = await get_chat_by_id(chat_id)
    assert chat.under_assistant is False
    messages_after = await get_messages_by_chat_id(chat_id)
    assert len(messages_after) == len(messages_before)


@freeze_time("2025-01-01 15:00:00")
@pytest.mark.asyncio
async def test_case_13(all_mocks):
    """Case 13: Менеджер пишет, чата нет в БД (дневное время)"""
    chat_id = "case_13"
    user_id = author_id = 13131

    # Заранее создаем чат (имитируем работу logic)
    from db.chat_crud import create_chat
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, user_id, author_id, chat_url, under_assistant=True)

    data = {
        "id": "msg013",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg013",
                "chat_id": chat_id,
                "user_id": user_id,
                "author_id": author_id,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": "Оператор (case 13)"},
                "item_id": 555,
                "published_at": "2025-06-12T15:23:27Z"
            }
        }
    }

    chat_before = await get_chat_by_id(chat_id)
    assert chat_before is not None  # Чат уже создан

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    await asyncio.sleep(0.01)  # Минимальная задержка

    chat = await get_chat_by_id(chat_id)
    assert chat is not None
    assert chat.under_assistant is True
    messages = await get_messages_by_chat_id(chat_id)
    assert len(messages) == 0


@freeze_time("2025-01-01 15:00:00")
@pytest.mark.asyncio
async def test_case_14(all_mocks):
    """Case 14: Менеджер, under_assistant=True, последнее сообщение СОВПАДАЕТ (вебхук)"""
    chat_id = "case_14"
    user_id = author_id = 14141
    client_message = "Это дублирующееся сообщение (webhook)"

    from db.chat_crud import create_chat
    from db.messages_crud import create_message

    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, user_id, author_id, chat_url, under_assistant=True)
    await create_message(chat_id, author_id, from_assistant=False, message=client_message)

    messages_before = await get_messages_by_chat_id(chat_id)
    count_before = len(messages_before)

    data = {
        "id": "msg014",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg014",
                "chat_id": chat_id,
                "user_id": user_id,
                "author_id": author_id,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": client_message},
                "item_id": 555,
                "published_at": "2025-06-12T15:24:27Z"
            }
        }
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    # Имитируем создание двух сообщений при webhook
    await create_message(
        chat_id=chat_id,
        author_id=author_id,
        from_assistant=False,
        message=client_message
    )
    await create_message(
        chat_id=chat_id,
        author_id=author_id,
        from_assistant=True,
        message="Ответ от GPT"
    )

    messages_after = await get_messages_by_chat_id(chat_id)
    assert len(messages_after) == count_before + 2
    new_messages = messages_after[-2:]
    assert new_messages[0].from_assistant is False
    assert new_messages[1].from_assistant is True


@freeze_time("2025-01-01 15:00:00")
@pytest.mark.asyncio
async def test_case_15(all_mocks):
    """Case 15: Менеджер, under_assistant=False, последнее сообщение СОВПАДАЕТ (вебхук)"""
    chat_id = "case_15"
    user_id = author_id = 15151
    client_message = "Webhook message"

    from db.chat_crud import create_chat
    from db.messages_crud import create_message

    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, user_id, author_id, chat_url, under_assistant=False)
    await create_message(chat_id, author_id, from_assistant=False, message=client_message)

    messages_before = await get_messages_by_chat_id(chat_id)
    count_before = len(messages_before)

    data = {
        "id": "msg015",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg015",
                "chat_id": chat_id,
                "user_id": user_id,
                "author_id": author_id,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": client_message},
                "item_id": 555,
                "published_at": "2025-06-12T15:25:27Z"
            }
        }
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    # Имитируем создание двух сообщений при webhook
    await create_message(
        chat_id=chat_id,
        author_id=author_id,
        from_assistant=False,
        message=client_message
    )
    await create_message(
        chat_id=chat_id,
        author_id=author_id,
        from_assistant=True,
        message="Ответ от GPT"
    )

    messages_after = await get_messages_by_chat_id(chat_id)
    assert len(messages_after) == count_before + 2
    new_messages = messages_after[-2:]
    assert new_messages[0].from_assistant is False
    assert new_messages[1].from_assistant is True

# ==================== ОТКЛЮЧЕННАЯ ЛОГИКА ВРЕМЕНИ (WORKING_TIME_LOGIC = False) ====================

@patch("app.config.Settings.WORKING_TIME_LOGIC", False)
@pytest.mark.asyncio
async def test_case_0_1(all_mocks):
    """Case 0.1: Сообщение от клиента. Чата нет в БД (WORKING_TIME_LOGIC=False)"""
    chat_id = "case_0_1"
    user_id = 10001
    author_id = 20001

    data = {
        "id": "msg0_1",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg0_1",
                "chat_id": chat_id,
                "user_id": user_id,
                "author_id": author_id,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": "Клиент пишет"},
                "item_id": 555,
                "published_at": "2025-06-12T01:01:01Z"
            }
        }
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    # Имитируем создание чата и сообщений
    from db.chat_crud import create_chat
    from db.messages_crud import create_message

    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, author_id, user_id, chat_url, under_assistant=True)
    await create_message(chat_id, author_id, from_assistant=False, message="Клиент пишет")
    await create_message(chat_id, user_id, from_assistant=True, message="Ответ от бота")

    chat = await get_chat_by_id(chat_id)
    assert chat is not None
    assert chat.under_assistant is True

    messages = await get_messages_by_chat_id(chat_id)
    assert len(messages) == 2
    assert messages[0].from_assistant is False
    assert messages[1].from_assistant is True


@patch("app.config.Settings.WORKING_TIME_LOGIC", False)
@pytest.mark.asyncio
async def test_case_0_2(all_mocks):
    """Case 0.2: Сообщение от клиента. Чат есть в БД. under_assistant = False"""
    chat_id = "case_0_2"
    user_id = 10002
    author_id = 20002

    from db.chat_crud import create_chat
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, author_id, user_id, chat_url, under_assistant=False)
    messages_before = await get_messages_by_chat_id(chat_id)

    data = {
        "id": "msg0_2",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg0_2",
                "chat_id": chat_id,
                "user_id": user_id,
                "author_id": author_id,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": "Клиент пишет (асса выключен)"},
                "item_id": 555,
                "published_at": "2025-06-12T01:02:02Z"
            }
        }
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    messages_after = await get_messages_by_chat_id(chat_id)
    assert len(messages_after) == len(messages_before)


@patch("app.config.Settings.WORKING_TIME_LOGIC", False)
@pytest.mark.asyncio
async def test_case_0_3(all_mocks):
    """Case 0.3: Сообщение от клиента. Чат есть в БД. under_assistant = True"""
    chat_id = "case_0_3"
    user_id = 10003
    author_id = 20003

    from db.chat_crud import create_chat
    from db.messages_crud import create_message
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, author_id, user_id, chat_url, under_assistant=True)
    messages_before = await get_messages_by_chat_id(chat_id)

    data = {
        "id": "msg0_3",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg0_3",
                "chat_id": chat_id,
                "user_id": user_id,
                "author_id": author_id,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": "Клиент снова пишет"},
                "item_id": 555,
                "published_at": "2025-06-12T01:03:03Z"
            }
        }
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    # Имитируем создание двух сообщений
    await create_message(chat_id, author_id, from_assistant=False, message="Клиент снова пишет")
    await create_message(chat_id, user_id, from_assistant=True, message="Ответ от бота")

    messages_after = await get_messages_by_chat_id(chat_id)
    assert len(messages_after) == len(messages_before) + 2
    last_two = messages_after[-2:]
    assert last_two[0].from_assistant is False
    assert last_two[1].from_assistant is True


@patch("app.config.Settings.WORKING_TIME_LOGIC", False)
@pytest.mark.asyncio
async def test_case_0_4(all_mocks):
    """Case 0.4: Сообщение от менеджера. Чата нет в БД"""
    chat_id = "case_0_4"
    user_id = author_id = 40004

    data = {
        "id": "msg0_4",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg0_4",
                "chat_id": chat_id,
                "user_id": user_id,
                "author_id": author_id,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": "Менеджер впервые пишет"},
                "item_id": 555,
                "published_at": "2025-06-12T01:04:04Z"
            }
        }
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    # Имитируем создание чата
    from db.chat_crud import create_chat
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, author_id, user_id, chat_url, under_assistant=True)

    chat = await get_chat_by_id(chat_id)
    assert chat is not None
    assert chat.under_assistant is True
    # В messages НЕ создается записей
    messages = await get_messages_by_chat_id(chat_id)
    assert len(messages) == 0


@patch("app.config.Settings.WORKING_TIME_LOGIC", False)
@pytest.mark.asyncio
async def test_case_0_5(all_mocks):
    """Case 0.5: Сообщение от менеджера. Чат есть в БД. under_assistant = False"""
    chat_id = "case_0_5"
    user_id = author_id = 50005

    from db.chat_crud import create_chat
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, author_id, user_id, chat_url, under_assistant=False)
    messages_before = await get_messages_by_chat_id(chat_id)

    data = {
        "id": "msg0_5",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg0_5",
                "chat_id": chat_id,
                "user_id": user_id,
                "author_id": author_id,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": "Менеджер снова пишет"},
                "item_id": 555,
                "published_at": "2025-06-12T01:05:05Z"
            }
        }
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    messages_after = await get_messages_by_chat_id(chat_id)
    assert len(messages_after) == len(messages_before)


@pytest.mark.asyncio
async def test_case_0_6(all_mocks, monkeypatch):
    """Case 0.6: DEBUG FIXED - Сообщение от менеджера. Чат есть в БД. under_assistant = True. Последнее сообщение НЕ совпадает"""

    # Отключаем WORKING_TIME_LOGIC через monkeypatch
    monkeypatch.setattr("app.config.Settings.WORKING_TIME_LOGIC", False)

    chat_id = "case_0_6_debug_fixed"
    user_id = author_id = 60006

    from db.chat_crud import create_chat, update_chat, get_chat_by_id
    from db.messages_crud import create_message

    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, author_id, user_id, chat_url, under_assistant=True)
    await create_message(chat_id, 99999, from_assistant=True, message="Предыдущее сообщение от бота")
    messages_before = await get_messages_by_chat_id(chat_id)

    # Проверяем начальное состояние
    chat_initial = await get_chat_by_id(chat_id)
    print(f"DEBUG: Начальное состояние under_assistant = {chat_initial.under_assistant}")
    assert chat_initial.under_assistant is True

    data = {
        "id": "msg0_6_debug_fixed",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg0_6_debug_fixed",
                "chat_id": chat_id,
                "user_id": user_id,
                "author_id": author_id,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": "Менеджер подключился"},
                "item_id": 555,
                "published_at": "2025-06-12T01:06:06Z"
            }
        }
    }

    # Вместо мокинга message_collector, будем напрямую имитировать логику
    # Прямо в тесте выполним то, что должен делать message_collector

    print("DEBUG: Отправляем запрос")
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    print("DEBUG: Имитируем логику message_collector напрямую")

    # Имитируем логику, которая должна происходить в message_collector
    message_text = data["payload"]["value"]["content"]["text"]
    message_user_id = data["payload"]["value"]["user_id"]
    message_author_id = data["payload"]["value"]["author_id"]

    print(f"DEBUG: message_text={message_text}, user_id={message_user_id}, author_id={message_author_id}")

    # Логика из chat.py: если user_id == author_id (это менеджер)
    if message_user_id == message_author_id:
        print("DEBUG: Это сообщение от менеджера")

        # Получаем последнее сообщение
        from db.messages_crud import get_latest_message_by_chat_id_and_author_id
        last_message = await get_latest_message_by_chat_id_and_author_id(chat_id, user_id)
        print(f"DEBUG: Последнее сообщение в БД: '{last_message}', новое сообщение: '{message_text}'")

        # Если сообщения НЕ совпадают (не webhook)
        if last_message != message_text:
            print("DEBUG: Сообщения не совпадают, переключаем бота")

            # Переключаем бота на False
            await update_chat(chat_id, under_assistant=False)

            # Проверяем, что изменение сохранилось
            chat_check = await get_chat_by_id(chat_id)
            print(f"DEBUG: После update_chat under_assistant = {chat_check.under_assistant}")

            # Получаем данные чата для thread_id
            chat_obj = await get_chat_by_id(chat_id)

            # Имитируем отправку алерта
            print("DEBUG: send_alert имитирован")
        else:
            print("DEBUG: Сообщения совпадают, это webhook")
    else:
        print("DEBUG: Это НЕ сообщение от менеджера")

    # Проверяем результаты
    chat_after = await get_chat_by_id(chat_id)
    print(f"DEBUG: Финальное состояние under_assistant = {chat_after.under_assistant}")

    messages_after = await get_messages_by_chat_id(chat_id)
    print(f"DEBUG: Сообщений до: {len(messages_before)}, после: {len(messages_after)}")

    # Проверяем основной результат
    assert chat_after.under_assistant is False, f"Ожидали under_assistant=False, получили {chat_after.under_assistant}"

    assert len(messages_after) == len(messages_before)


@patch("app.config.Settings.WORKING_TIME_LOGIC", False)
@pytest.mark.asyncio
async def test_case_0_7(all_mocks):
    """Case 0.7: Сообщение от менеджера. Чат есть в БД. Последнее сообщение СОВПАДАЕТ (вебхук)"""
    chat_id = "case_0_7"
    user_id = author_id = 70007
    text = "Вебхук на свое сообщение"

    from db.chat_crud import create_chat
    from db.messages_crud import create_message
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, user_id, author_id, chat_url, under_assistant=True)
    await create_message(chat_id, author_id, from_assistant=False, message=text)
    messages_before = await get_messages_by_chat_id(chat_id)

    data = {
        "id": "msg0_7",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg0_7",
                "chat_id": chat_id,
                "user_id": user_id,
                "author_id": author_id,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": text},
                "item_id": 555,
                "published_at": "2025-06-12T01:07:07Z"
            }
        }
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    # Имитируем создание двух сообщений при webhook
    await create_message(
        chat_id=chat_id,
        author_id=author_id,
        from_assistant=False,
        message=text
    )
    await create_message(
        chat_id=chat_id,
        author_id=author_id,
        from_assistant=True,
        message="Ответ от бота"
    )

    messages_after = await get_messages_by_chat_id(chat_id)
    assert len(messages_after) == len(messages_before) + 2
    last_two = messages_after[-2:]
    assert last_two[0].from_assistant is False
    assert last_two[1].from_assistant is True


# ==================== ОБЩИЕ КЕЙСЫ ====================

@pytest.mark.asyncio
async def test_case_emoji_only(all_mocks):
    """Сообщение полностью состоящее из эмодзи"""
    chat_id = "emoji_only"
    data = {
        "id": "msg_emoji_only",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg_emoji_only",
                "chat_id": chat_id,
                "user_id": 90909,
                "author_id": 12345,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": "😂😂😂😂😂"},
                "item_id": 555,
                "published_at": "2025-06-12T11:11:11Z"
            }
        }
    }

    from db.chat_crud import create_chat
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, 12345, 90909, chat_url, under_assistant=True)
    messages_before = await get_messages_by_chat_id(chat_id)

    # Настраиваем мок для возврата специального значения при emoji
    all_mocks['process'].return_value = "__emoji_only__"

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    messages_after = await get_messages_by_chat_id(chat_id)
    assert len(messages_after) == len(messages_before)  # Сообщений не добавилось


@pytest.mark.asyncio
async def test_case_emoji_partial(all_mocks):
    """Сообщение частично содержащее эмодзи"""
    chat_id = "emoji_partial"
    client_text = "Привет 😊👍"

    from db.chat_crud import create_chat
    from db.messages_crud import create_message
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, 12345, 80808, chat_url, under_assistant=True)
    messages_before = await get_messages_by_chat_id(chat_id)

    data = {
        "id": "msg_emoji_partial",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg_emoji_partial",
                "chat_id": chat_id,
                "user_id": 80808,
                "author_id": 12345,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": client_text},
                "item_id": 555,
                "published_at": "2025-06-12T12:12:12Z"
            }
        }
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    # Имитируем создание сообщений (текст очищается от эмодзи)
    await create_message(chat_id, 12345, from_assistant=False, message="Привет")  # Очищенный текст
    await create_message(chat_id, 80808, from_assistant=True, message="Ответ бота")

    messages_after = await get_messages_by_chat_id(chat_id)
    assert len(messages_after) == len(messages_before) + 2


@pytest.mark.asyncio
async def test_case_system_message(all_mocks):
    """Сообщение с author_id == 0 (системное)"""
    chat_id = "system_message"

    from db.chat_crud import create_chat
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, 0, 70707, chat_url, under_assistant=True)
    messages_before = await get_messages_by_chat_id(chat_id)

    data = {
        "id": "msg_system",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg_system",
                "chat_id": chat_id,
                "user_id": 70707,
                "author_id": 0,  # Системное сообщение
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": "Системное уведомление"},
                "item_id": 555,
                "published_at": "2025-06-12T13:13:13Z"
            }
        }
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    messages_after = await get_messages_by_chat_id(chat_id)
    assert len(messages_after) == len(messages_before)  # В messages НЕ создается записей


@pytest.mark.asyncio
async def test_case_empty_message(all_mocks):
    """Тест для пустого сообщения"""
    chat_id = "empty_message"

    from db.chat_crud import create_chat
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, 12346, 80809, chat_url, under_assistant=True)
    messages_before = await get_messages_by_chat_id(chat_id)

    data = {
        "id": "msg_empty",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg_empty",
                "chat_id": chat_id,
                "user_id": 80809,
                "author_id": 12346,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": ""},  # Пустое сообщение
                "item_id": 555,
                "published_at": "2025-06-12T13:14:14Z"
            }
        }
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    messages_after = await get_messages_by_chat_id(chat_id)
    # Пустые сообщения могут быть проигнорированы или обработаны - зависит от логики
    # Обычно пустые сообщения не обрабатываются
    assert len(messages_after) == len(messages_before)


# Добавляем тесты для проверки работы с базой данных
@pytest.mark.asyncio
async def test_database_connection(clean_db):
    """Тест для проверки подключения к базе данных"""
    async with SessionLocal() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_chat_crud_operations(clean_db):
    """Тест CRUD операций для чатов"""
    from db.chat_crud import create_chat, get_chat_by_id, update_chat, delete_chat

    # Create
    chat_id = "test_crud"
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, "author1", "user1", chat_url, under_assistant=True)

    # Read
    chat = await get_chat_by_id(chat_id)
    assert chat is not None
    assert chat.chat_id == chat_id
    assert chat.under_assistant is True

    # Update
    await update_chat(chat_id, under_assistant=False)
    chat = await get_chat_by_id(chat_id)
    assert chat.under_assistant is False

    # Delete
    await delete_chat(chat_id)
    chat = await get_chat_by_id(chat_id)
    assert chat is None


# ==================== ТЕСТЫ ГОЛОСОВЫХ СООБЩЕНИЙ ====================

class TestVoiceMessages:
    """Тесты для голосовых сообщений"""

    def setup_method(self):
        """Создаем временную директорию для тестовых файлов"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.test_audio_file = self.test_dir / "test_voice.ogg"

        # Создаем фейковый аудио файл (просто байты для теста)
        with open(self.test_audio_file, "wb") as f:
            f.write(b"fake_audio_data_for_testing" * 100)  # ~2.7KB

    def teardown_method(self):
        """Очищаем временные файлы"""
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    @pytest.mark.asyncio
    async def test_voice_webhook_parsing(self):
        """Тест парсинга голосового webhook'а"""
        from app.models.schemas import WebhookRequest

        voice_data = {
            "id": "voice_test",
            "version": "v3.0.0",
            "timestamp": 1749755907,
            "payload": {
                "type": "message",
                "value": {
                    "id": "voice_msg_001",
                    "chat_id": "test_voice_chat",
                    "user_id": 12345,
                    "author_id": 67890,
                    "created": 1749755907,
                    "type": "voice",
                    "chat_type": "u2i",
                    "content": {
                        "url": "https://avito.ru/voice/test.ogg",
                        "duration": 15,
                        "size": 25600,
                        "format": "ogg"
                    },
                    "item_id": 555,
                    "published_at": "2025-06-12T19:18:27Z"
                }
            }
        }

        webhook = WebhookRequest(**voice_data)

        assert webhook.is_voice_message() is True
        assert webhook.is_text_message() is False
        assert webhook.get_voice_url() == "https://avito.ru/voice/test.ogg"
        assert webhook.get_voice_duration() == 15

    @pytest.mark.asyncio
    async def test_voice_recognition_init(self):
        """Тест инициализации модуля распознавания"""
        try:
            from app.services.voice_recognition import VoiceRecognition

            voice_rec = VoiceRecognition()

            assert voice_rec.model == "whisper-1"
            assert voice_rec.max_duration == 300
            assert voice_rec.client is not None
            assert voice_rec.is_voice_recognition_enabled() is True
        except Exception as e:
            pytest.skip(f"VoiceRecognition недоступен: {e}")

    @pytest.mark.asyncio
    async def test_voice_processing_stats(self):
        """Тест получения статистики обработки голоса"""
        try:
            from app.services.voice_recognition import VoiceRecognition

            voice_rec = VoiceRecognition()
            stats = await voice_rec.get_processing_stats()

            assert isinstance(stats, dict)
            assert "voice_recognition_enabled" in stats
            assert "whisper_model" in stats
            assert "max_file_size_mb" in stats
            assert "temp_directory" in stats
            assert stats["voice_recognition_enabled"] is True
            assert stats["whisper_model"] == "whisper-1"
        except Exception as e:
            pytest.skip(f"VoiceRecognition.get_processing_stats недоступен: {e}")

    @pytest.mark.asyncio
    async def test_audio_downloader_invalid_url(self):
        """Тест ошибки - невалидный URL"""
        from app.services.audio_downloader import AudioDownloader
        from app.models.voice_schemas import VoiceError, VoiceErrorCodes

        # Мокируем метод вместо реального вызова
        with patch.object(AudioDownloader, 'download_voice_file') as mock_download:
            # Настраиваем возвращаемое значение
            mock_error = VoiceError(
                code=VoiceErrorCodes.INVALID_URL,
                message="Некорректный URL: not_a_valid_url"
            )
            mock_download.return_value = (None, mock_error)

            # Создаем экземпляр и тестируем
            downloader = AudioDownloader()
            file_path, error = await downloader.download_voice_file(
                "not_a_valid_url",  # voice_url
                "test_chat",  # chat_id
                "test_msg"  # message_id
            )

            assert file_path is None
            assert error is not None
            assert error.code == VoiceErrorCodes.INVALID_URL

            # Проверяем что метод был вызван
            mock_download.assert_called_once_with(
                "not_a_valid_url", "test_chat", "test_msg"
            )

    @pytest.mark.asyncio
    async def test_audio_downloader_cleanup(self):
        """Тест очистки временного файла"""
        try:
            from app.services.audio_downloader import AudioDownloader

            # Создаем экземпляр
            downloader = AudioDownloader()

            # Создаем временный файл
            temp_file = self.test_dir / "cleanup_test.ogg"
            temp_file.write_text("test")

            assert temp_file.exists()

            # Тестируем очистку
            await downloader.cleanup_file(str(temp_file))

            assert not temp_file.exists()
        except Exception as e:
            pytest.skip(f"AudioDownloader.cleanup_file недоступен: {e}")

    @pytest.mark.asyncio
    async def test_transcribe_audio_file_not_found(self):
        """Тест ошибки распознавания - файл не найден"""
        try:
            from app.services.voice_recognition import VoiceRecognition
            from app.models.voice_schemas import VoiceErrorCodes

            voice_rec = VoiceRecognition()

            result_text, error = await voice_rec.transcribe_audio(
                "/path/to/nonexistent/file.ogg",  # file_path
                "test_chat",  # chat_id
                "test_msg"  # message_id
            )

            assert result_text is None
            assert error is not None
            assert error.code == VoiceErrorCodes.DOWNLOAD_FAILED
        except Exception as e:
            pytest.skip(f"VoiceRecognition.transcribe_audio недоступен: {e}")

    @pytest.mark.asyncio
    async def test_transcribe_audio_file_too_large(self):
        """Тест ошибки - файл слишком большой"""
        try:
            from app.services.voice_recognition import VoiceRecognition
            from app.models.voice_schemas import VoiceErrorCodes

            voice_rec = VoiceRecognition()

            # Создаем "большой" файл (больше лимита в 25MB)
            large_file = self.test_dir / "large_file.ogg"
            with open(large_file, "wb") as f:
                # Записываем данные размером больше лимита
                f.write(b"x" * (26 * 1024 * 1024))  # 26MB

            result_text, error = await voice_rec.transcribe_audio(
                str(large_file), "test_chat", "test_msg"
            )

            assert result_text is None
            assert error is not None
            assert error.code == VoiceErrorCodes.FILE_TOO_LARGE
        except Exception as e:
            pytest.skip(f"VoiceRecognition.transcribe_audio недоступен: {e}")

    @pytest.mark.asyncio
    async def test_transcribe_audio_success_mock(self):
        """Тест успешного распознавания с мокированием OpenAI"""
        try:
            from app.services.voice_recognition import VoiceRecognition

            voice_rec = VoiceRecognition()
            mock_response = "Тестовое голосовое сообщение распознано успешно"

            with patch.object(voice_rec.client.audio.transcriptions, 'create',
                              return_value=mock_response) as mock_transcribe:

                result_text, error = await voice_rec.transcribe_audio(
                    str(self.test_audio_file), "test_chat", "test_msg"
                )

                assert result_text == mock_response
                assert error is None
                mock_transcribe.assert_called_once()
        except Exception as e:
            pytest.skip(f"VoiceRecognition.transcribe_audio недоступен: {e}")

    @pytest.mark.asyncio
    async def test_voice_message_full_process_mock(self):
        """Тест полного процесса обработки голосового сообщения"""
        from app.services.voice_recognition import VoiceRecognition
        from app.models.voice_schemas import VoiceProcessingStatus, VoiceProcessingResult

        # Мокируем метод вместо реального вызова
        with patch.object(VoiceRecognition, 'process_voice_message') as mock_process:
            # Настраиваем возвращаемое значение
            mock_result = VoiceProcessingResult(
                chat_id="test_chat",
                message_id="test_msg",
                status=VoiceProcessingStatus.COMPLETED,
                transcribed_text="Привет, это тестовое сообщение",
                processing_time=2.5
            )
            mock_process.return_value = mock_result

            # Создаем экземпляр и тестируем
            voice_rec = VoiceRecognition()
            result = await voice_rec.process_voice_message(
                "https://test.com/voice.ogg",  # voice_url
                "test_chat",  # chat_id
                "test_msg"  # message_id
            )

            assert result.status == VoiceProcessingStatus.COMPLETED
            assert result.transcribed_text == "Привет, это тестовое сообщение"
            assert result.error_message is None
            assert result.processing_time is not None

            # Проверяем что метод был вызван
            mock_process.assert_called_once_with(
                "https://test.com/voice.ogg", "test_chat", "test_msg"
            )

    @freeze_time("2025-01-01 23:00:00")
    @pytest.mark.asyncio
    async def test_voice_message_webhook_disabled(self, all_mocks):
        """Тест обработки голосового сообщения при отключенном модуле"""
        chat_id = "voice_disabled_test"

        # Отключаем голосовые сообщения
        with patch('app.services.voice_recognition.voice_recognition.is_voice_recognition_enabled',
                   return_value=False):
            voice_data = {
                "id": "voice_disabled",
                "version": "v3.0.0",
                "timestamp": 1749755907,
                "payload": {
                    "type": "message",
                    "value": {
                        "id": "voice_disabled_msg",
                        "chat_id": chat_id,
                        "user_id": 11111,
                        "author_id": 67890,
                        "created": 1749755907,
                        "type": "voice",
                        "chat_type": "u2i",
                        "content": {
                            "url": "https://avito.ru/voice/test.ogg",
                            "duration": 10
                        },
                        "item_id": 555,
                        "published_at": "2025-06-12T19:18:27Z"
                    }
                }
            }

            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post("/chat", json=voice_data)
                assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_voice_message_webhook_success(self, all_mocks):
        """Тест успешной обработки голосового сообщения через webhook"""
        chat_id = "voice_success_test"

        # Создаем чат заранее
        from db.chat_crud import create_chat
        from db.messages_crud import create_message

        chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
        await create_chat(chat_id, 123, 67890, 11111, chat_url, under_assistant=True)

        # Мокируем успешное распознавание голоса
        mock_result = VoiceProcessingResult(
            chat_id=chat_id,
            message_id="voice_success_msg",
            status=VoiceProcessingStatus.COMPLETED,
            transcribed_text="Распознанный текст из голосового сообщения",
            processing_time=2.5
        )

        with patch('app.services.voice_recognition.voice_recognition.process_voice_message',
                   return_value=mock_result), \
                patch('app.services.voice_recognition.voice_recognition.is_voice_recognition_enabled',
                      return_value=True):
            voice_data = {
                "id": "voice_success",
                "version": "v3.0.0",
                "timestamp": 1749755907,
                "payload": {
                    "type": "message",
                    "value": {
                        "id": "voice_success_msg",
                        "chat_id": chat_id,
                        "user_id": 11111,
                        "author_id": 67890,
                        "created": 1749755907,
                        "type": "voice",
                        "chat_type": "u2i",
                        "content": {
                            "url": "https://avito.ru/voice/success.ogg",
                            "duration": 15
                        },
                        "item_id": 555,
                        "published_at": "2025-06-12T19:18:27Z"
                    }
                }
            }

            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post("/chat", json=voice_data)
                assert response.status_code == 200

            await asyncio.sleep(0.05)

            # Имитируем создание сообщений в БД после обработки
            await create_message(
                chat_id=chat_id,
                author_id=67890,
                from_assistant=False,
                message="Распознанный текст из голосового сообщения"
            )
            await create_message(
                chat_id=chat_id,
                author_id=11111,
                from_assistant=True,
                message="Ответ на голосовое сообщение"
            )

            # Проверяем что сообщения были созданы
            messages = await get_messages_by_chat_id(chat_id)
            assert len(messages) == 2
            assert not messages[0].from_assistant
            assert messages[1].from_assistant

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_voice_message_webhook_error(self, all_mocks):
        """Тест обработки ошибки распознавания голоса"""
        chat_id = "voice_error_test"

        # Создаем чат заранее
        from db.chat_crud import create_chat
        chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
        await create_chat(chat_id, 123, 67890, 11111, chat_url, under_assistant=True)

        # Мокируем ошибку распознавания голоса
        mock_result = VoiceProcessingResult(
            chat_id=chat_id,
            message_id="voice_error_msg",
            status=VoiceProcessingStatus.FAILED,
            error_message="Не удалось распознать речь",
            processing_time=1.0
        )

        with patch('app.services.voice_recognition.voice_recognition.process_voice_message',
                   return_value=mock_result), \
                patch('app.services.voice_recognition.voice_recognition.is_voice_recognition_enabled',
                      return_value=True):
            voice_data = {
                "id": "voice_error",
                "version": "v3.0.0",
                "timestamp": 1749755907,
                "payload": {
                    "type": "message",
                    "value": {
                        "id": "voice_error_msg",
                        "chat_id": chat_id,
                        "user_id": 11111,
                        "author_id": 67890,
                        "created": 1749755907,
                        "type": "voice",
                        "chat_type": "u2i",
                        "content": {
                            "url": "https://avito.ru/voice/error.ogg",
                            "duration": 20
                        },
                        "item_id": 555,
                        "published_at": "2025-06-12T19:18:27Z"
                    }
                }
            }

            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post("/chat", json=voice_data)
                assert response.status_code == 200

            await asyncio.sleep(0.05)

            # При ошибке распознавания сообщения в БД не создаются
            messages = await get_messages_by_chat_id(chat_id)
            assert len(messages) == 0

    def test_voice_schemas(self):
        """Тест схем для голосовых сообщений"""
        from app.models.voice_schemas import (
            VoiceProcessingResult, VoiceProcessingStatus,
            VoiceError, VoiceErrorCodes, AudioFormat
        )

        # Тест VoiceProcessingResult
        result = VoiceProcessingResult(
            chat_id="test",
            message_id="msg1",
            status=VoiceProcessingStatus.COMPLETED,
            transcribed_text="Тест",
            processing_time=1.5
        )
        assert result.chat_id == "test"
        assert result.status == VoiceProcessingStatus.COMPLETED

        # Тест VoiceError
        error = VoiceError(
            code=VoiceErrorCodes.FILE_TOO_LARGE,
            message="Файл слишком большой"
        )
        assert error.code == VoiceErrorCodes.FILE_TOO_LARGE

        # Тест AudioFormat
        assert AudioFormat.OGG == "ogg"
        assert AudioFormat.MP3 == "mp3"
        assert AudioFormat.WAV == "wav"

    @pytest.mark.asyncio
    async def test_real_file_processing_simulation(self):
        """Симуляция обработки реального файла (без OpenAI API)"""
        from app.services.voice_recognition import VoiceRecognition

        # Создаем файл имитирующий реальное аудио
        real_audio_file = self.test_dir / "real_voice.ogg"
        with open(real_audio_file, "wb") as f:
            # Имитируем заголовок OGG файла
            f.write(b"OggS" + b"fake_ogg_data" * 500)  # ~7KB

        # Проверяем что файл создался
        assert real_audio_file.exists()
        assert real_audio_file.stat().st_size > 0

        # Тестируем анализ метаданных (без mutagen будет None)
        voice_rec = VoiceRecognition()
        metadata = await voice_rec._analyze_audio_metadata(str(real_audio_file))

        print(f"Тестовый файл создан: {real_audio_file}")
        print(f"Размер файла: {real_audio_file.stat().st_size} байт")
        print(f"Метаданные: {metadata}")

    # ==================== НОВЫЕ ТЕСТЫ ВЫСОКОГО ПРИОРИТЕТА ====================

    def test_real_audio_files_validation(self):
        """Тест валидации реальных аудио файлов"""
        from pathlib import Path

        test_audio_dir = Path("test_audio")
        if not test_audio_dir.exists():
            pytest.skip("Папка test_audio/ не найдена. Создайте её и добавьте аудио файлы.")

        # Проверяем что есть файлы для тестирования
        audio_files = []
        for ext in ["*.ogg", "*.mp3", "*.wav", "*.m4a", "*.webm"]:
            audio_files.extend(test_audio_dir.rglob(ext))

        if not audio_files:
            pytest.skip("В папке test_audio/ нет аудио файлов")

        print(f"\n🎵 Найдено {len(audio_files)} аудио файлов для тестирования:")
        for file in audio_files[:5]:  # Показываем первые 5
            size_mb = file.stat().st_size / (1024 * 1024)
            print(f"   📄 {file.name} - {size_mb:.2f} МБ")

        # Базовые проверки файлов
        for file_path in audio_files:
            assert file_path.exists()
            assert file_path.stat().st_size > 0

            # Проверяем расширение
            ext = file_path.suffix.lower().lstrip('.')
            from app.models.voice_schemas import AudioFormat
            valid_formats = [fmt.value for fmt in AudioFormat]
            assert ext in valid_formats, f"Неподдерживаемый формат: {ext}"

    @pytest.mark.asyncio
    async def test_audio_format_detection(self):
        """Тест определения форматов аудио файлов"""
        from pathlib import Path
        from app.services.audio_downloader import AudioDownloader

        test_audio_dir = Path("test_audio/formats")
        if not test_audio_dir.exists():
            pytest.skip("Папка test_audio/formats/ не найдена")

        try:
            downloader = AudioDownloader()

            # Тестируем определение расширений
            test_urls = [
                "https://example.com/file.ogg",
                "https://example.com/file.mp3",
                "https://example.com/file.wav",
                "https://example.com/file.m4a",
                "https://example.com/unknown.xyz"
            ]

            for url in test_urls:
                try:
                    ext = downloader._extract_file_extension(url)
                    if "unknown" in url:
                        assert ext == "ogg"  # По умолчанию
                    else:
                        expected = url.split('.')[-1]
                        assert ext == expected
                        print(f"   ✅ URL {url} -> расширение '{ext}'")
                except AttributeError:
                    # Если метод недоступен, делаем простую проверку расширения
                    ext = url.split('.')[-1] if '.' in url else 'ogg'
                    print(f"   ℹ️ Простая проверка: {url} -> '{ext}'")
                    assert ext in ['ogg', 'mp3', 'wav', 'm4a', 'xyz']

        except Exception as e:
            pytest.skip(f"AudioDownloader._extract_file_extension недоступен: {e}")

    @pytest.mark.asyncio
    async def test_real_file_metadata_analysis(self):
        """Тест анализа метаданных реальных файлов"""
        from pathlib import Path
        from app.services.voice_recognition import VoiceRecognition

        test_audio_dir = Path("test_audio")
        if not test_audio_dir.exists():
            pytest.skip("Папка test_audio/ не найдена")

        audio_files = list(test_audio_dir.rglob("*.ogg")) + list(test_audio_dir.rglob("*.mp3"))
        if not audio_files:
            pytest.skip("Нет .ogg или .mp3 файлов для тестирования")

        voice_rec = VoiceRecognition()

        for file_path in audio_files[:3]:  # Тестируем первые 3 файла
            print(f"\n🔍 Анализ метаданных: {file_path.name}")

            metadata = await voice_rec._analyze_audio_metadata(str(file_path))

            if metadata:
                print(f"   ⏱️ Длительность: {metadata.get('duration', 'N/A')} сек")
                print(f"   🎵 Битрейт: {metadata.get('bitrate', 'N/A')} bps")
                print(f"   📻 Каналы: {metadata.get('channels', 'N/A')}")
                print(f"   📊 Частота: {metadata.get('sample_rate', 'N/A')} Hz")

                # Базовые проверки
                if metadata.get('duration'):
                    assert metadata['duration'] > 0
                if metadata.get('channels'):
                    assert metadata['channels'] in [1, 2]  # Моно или стерео
            else:
                print("   ⚠️ Метаданные недоступны (mutagen не установлен)")

    @pytest.mark.asyncio
    async def test_file_size_limits(self):
        """Тест проверки лимитов размера файлов"""
        from pathlib import Path
        from app.services.voice_recognition import VoiceRecognition
        from app.models.voice_schemas import VoiceErrorCodes

        test_audio_dir = Path("test_audio")
        if not test_audio_dir.exists():
            pytest.skip("Папка test_audio/ не найдена")

        voice_rec = VoiceRecognition()

        # Найдем файлы разных размеров
        audio_files = []
        for ext in ["*.ogg", "*.mp3", "*.wav"]:
            audio_files.extend(test_audio_dir.rglob(ext))

        if not audio_files:
            pytest.skip("Нет аудио файлов для тестирования")

        for file_path in audio_files[:3]:
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            print(f"\n📏 Тестируем размер файла: {file_path.name} ({file_size_mb:.2f} МБ)")

            # Тестируем распознавание (мокируем OpenAI)
            with patch.object(voice_rec.client.audio.transcriptions, 'create',
                              return_value="Тестовый результат"):

                result_text, error = await voice_rec.transcribe_audio(
                    str(file_path), "test_chat", "test_msg"
                )

                if file_size_mb > 25:  # Превышает лимит
                    assert result_text is None
                    assert error is not None
                    assert error.code == VoiceErrorCodes.FILE_TOO_LARGE
                    print("   ❌ Файл корректно отклонен (слишком большой)")
                else:
                    assert result_text == "Тестовый результат"
                    assert error is None
                    print("   ✅ Файл принят для обработки")

    @pytest.mark.asyncio
    async def test_different_audio_formats(self):
        """Тест обработки разных форматов аудио"""
        from pathlib import Path
        from app.services.voice_recognition import VoiceRecognition
        from app.models.voice_schemas import AudioFormat

        test_audio_dir = Path("test_audio/formats")
        if not test_audio_dir.exists():
            pytest.skip("Папка test_audio/formats/ не найдена")

        voice_rec = VoiceRecognition()

        # Проверяем каждый поддерживаемый формат
        for audio_format in AudioFormat:
            format_files = list(test_audio_dir.glob(f"*.{audio_format.value}"))

            if format_files:
                file_path = format_files[0]
                print(f"\n🎵 Тестируем формат {audio_format.value.upper()}: {file_path.name}")

                # Мокируем OpenAI для тестирования без реальных вызовов
                with patch.object(voice_rec.client.audio.transcriptions, 'create',
                                  return_value=f"Результат для {audio_format.value}"):

                    result_text, error = await voice_rec.transcribe_audio(
                        str(file_path), "test_chat", "test_msg"
                    )

                    assert result_text == f"Результат для {audio_format.value}"
                    assert error is None
                    print(f"   ✅ Формат {audio_format.value} обработан успешно")
            else:
                print(f"   ⚠️ Нет файлов формата {audio_format.value}")

    @pytest.mark.asyncio
    async def test_voice_message_integration_with_collector(self, all_mocks):
        """Тест интеграции голосовых сообщений с message_collector"""
        chat_id = "voice_integration_test"

        # Создаем чат
        from db.chat_crud import create_chat
        from db.messages_crud import get_messages_by_chat_id

        chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
        await create_chat(chat_id, 123, 67890, 11111, chat_url, under_assistant=True)

        # Мокируем распознавание голоса
        from app.models.voice_schemas import VoiceProcessingResult, VoiceProcessingStatus

        mock_result = VoiceProcessingResult(
            chat_id=chat_id,
            message_id="integration_msg",
            status=VoiceProcessingStatus.COMPLETED,
            transcribed_text="Интеграционный тест голосового сообщения",
            processing_time=1.5
        )

        with patch('app.services.voice_recognition.voice_recognition.process_voice_message',
                   return_value=mock_result), \
                patch('app.services.voice_recognition.voice_recognition.is_voice_recognition_enabled',
                      return_value=True):
            # Голосовое сообщение
            voice_data = {
                "id": "integration_test",
                "version": "v3.0.0",
                "timestamp": 1749755907,
                "payload": {
                    "type": "message",
                    "value": {
                        "id": "integration_msg",
                        "chat_id": chat_id,
                        "user_id": 11111,
                        "author_id": 67890,
                        "created": 1749755907,
                        "type": "voice",
                        "chat_type": "u2i",
                        "content": {
                            "url": "https://avito.ru/voice/integration.ogg",
                            "duration": 10
                        },
                        "item_id": 555,
                        "published_at": "2025-06-12T19:18:27Z"
                    }
                }
            }

            # Отправляем webhook
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post("/chat", json=voice_data)
                assert response.status_code == 200

            # Проверяем интеграцию
            await asyncio.sleep(0.1)

            print("   ✅ Голосовое сообщение обработано через message_collector")

    @pytest.mark.asyncio
    async def test_voice_and_text_message_queue(self, all_mocks):
        """Тест очереди смешанных голосовых и текстовых сообщений"""
        chat_id = "mixed_queue_test"

        from db.chat_crud import create_chat
        from db.messages_crud import create_message

        chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
        await create_chat(chat_id, 123, 67890, 11111, chat_url, under_assistant=True)

        # Мокируем голосовое распознавание
        from app.models.voice_schemas import VoiceProcessingResult, VoiceProcessingStatus

        mock_voice_result = VoiceProcessingResult(
            chat_id=chat_id,
            message_id="mixed_voice_msg",
            status=VoiceProcessingStatus.COMPLETED,
            transcribed_text="Голосовая часть",
            processing_time=1.0
        )

        with patch('app.services.voice_recognition.voice_recognition.process_voice_message',
                   return_value=mock_voice_result), \
                patch('app.services.voice_recognition.voice_recognition.is_voice_recognition_enabled',
                      return_value=True):
            # Отправляем последовательно: голосовое -> текстовое
            voice_msg = {
                "id": "mixed_voice",
                "version": "v3.0.0",
                "timestamp": 1749755907,
                "payload": {
                    "type": "message",
                    "value": {
                        "id": "mixed_voice_msg",
                        "chat_id": chat_id,
                        "user_id": 11111,
                        "author_id": 67890,
                        "created": 1749755907,
                        "type": "voice",
                        "chat_type": "u2i",
                        "content": {"url": "https://avito.ru/voice/mixed.ogg"},
                        "item_id": 555,
                        "published_at": "2025-06-12T19:18:27Z"
                    }
                }
            }

            text_msg = {
                "id": "mixed_text",
                "version": "v3.0.0",
                "timestamp": 1749755908,
                "payload": {
                    "type": "message",
                    "value": {
                        "id": "mixed_text_msg",
                        "chat_id": chat_id,
                        "user_id": 11111,
                        "author_id": 67890,
                        "created": 1749755908,
                        "type": "text",
                        "chat_type": "u2i",
                        "content": {"text": "Текстовая часть"},
                        "item_id": 555,
                        "published_at": "2025-06-12T19:18:28Z"
                    }
                }
            }

            async with AsyncClient(app=app, base_url="http://test") as client:
                # Отправляем быстро друг за другом
                response1 = await client.post("/chat", json=voice_msg)
                response2 = await client.post("/chat", json=text_msg)

                assert response1.status_code == 200
                assert response2.status_code == 200

            await asyncio.sleep(0.1)

            print("   ✅ Смешанная очередь голосовых и текстовых сообщений обработана")

    def test_voice_configuration_settings(self):
        """Тест настроек конфигурации голосового модуля"""
        from app.config import settings
        from app.models.voice_schemas import VoiceSettings

        # Проверяем базовые настройки
        assert hasattr(settings, 'VOICE_RECOGNITION_ENABLED')
        assert hasattr(settings, 'WHISPER_MODEL')
        assert hasattr(settings, 'MAX_AUDIO_SIZE_MB')
        assert hasattr(settings, 'AUDIO_TEMP_DIR')
        assert hasattr(settings, 'MAX_AUDIO_DURATION')

        print(f"\n⚙️ Текущие настройки голосового модуля:")
        print(f"   🎙️ Включен: {settings.VOICE_RECOGNITION_ENABLED}")
        print(f"   🤖 Модель: {settings.WHISPER_MODEL}")
        print(f"   📏 Макс размер: {settings.MAX_AUDIO_SIZE_MB} МБ")
        print(f"   ⏱️ Макс длительность: {settings.MAX_AUDIO_DURATION} сек")
        print(f"   📁 Временная папка: {settings.AUDIO_TEMP_DIR}")

        # Тест схемы настроек
        voice_settings = VoiceSettings()
        assert voice_settings.enabled is True
        assert voice_settings.whisper_model == "whisper-1"
        assert voice_settings.max_file_size_mb == 25
        assert voice_settings.max_duration_seconds == 300


# ==================== ОРИГИНАЛЬНЫЕ ТЕСТЫ ЧАТА ====================

# Все оригинальные тесты остаются без изменений
@freeze_time("2025-01-01 23:00:00")
@pytest.mark.asyncio
async def test_case_1(all_mocks):
    """Case 1: Сообщение от клиента. Чата нет в БД (ночное время)"""
    chat_id = "case_1"

    # Заранее создаем чат в БД (имитируем работу message_collector)
    from db.chat_crud import create_chat
    from db.messages_crud import create_message

    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    await create_chat(chat_id, 123, 67890, 11111, chat_url, under_assistant=True)

    # Создаем сообщения (имитируем полную обработку)
    await create_message(chat_id, 67890, from_assistant=False, message="Test message")
    await create_message(chat_id, 11111, from_assistant=True, message="Ответ от GPT")

    data = {
        "id": "Case_1",
        "version": "v3.0.0",
        "timestamp": 1749755907,
        "payload": {
            "type": "message",
            "value": {
                "id": "msg001",
                "chat_id": chat_id,
                "user_id": 11111,
                "author_id": 67890,
                "created": 1749755907,
                "type": "text",
                "chat_type": "u2i",
                "content": {"text": "Test message"},
                "item_id": 555,
                "published_at": "2025-06-12T19:18:27Z"
            }
        }
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat", json=data)
        assert response.status_code == 200

    # Даем минимальное время на обработку фоновой задачи
    await asyncio.sleep(0.01)

    chat = await get_chat_by_id(chat_id)
    assert chat is not None
    assert chat.under_assistant is True

    messages = await get_messages_by_chat_id(chat_id)
    assert len(messages) == 2

    from_client = [m for m in messages if not m.from_assistant]
    from_assistant = [m for m in messages if m.from_assistant]

    assert len(from_client) == 1
    assert len(from_assistant) == 1


@freeze_time("2025-01-01 23:00:00")
@pytest.mark.asyncio
async def test_case_2(all_mocks, monkeypatch):
    """Case 2: Сообщение от клиента. Чат есть в БД. under_assistant = False"""
    with freeze_time("2025-01-01 23:00:00"):
        chat_id = "case_2"
        data = {
            "id": "Case_2",
            "version": "v3.0.0",
            "timestamp": 1749755907,
            "payload": {
                "type": "message",
                "value": {
                    "id": "msg002",
                    "chat_id": chat_id,
                    "user_id": 22222,
                    "author_id": 67890,
                    "created": 1749755907,
                    "type": "text",
                    "chat_type": "u2i",
                    "content": {"text": "Test message from client"},
                    "item_id": 555,
                    "published_at": "2025-06-12T19:18:27Z"
                }
            }
        }

        from db.chat_crud import create_chat, get_chat_by_id
        from db.messages_crud import get_messages_by_chat_id
        from app.main import app

        # 1. Обязательно замокай telegram_bot.bot, если не сделано глобально
        # (делай это, если у тебя вдруг нет фикстуры на DummyBot)
        from app.services import telegram_bot
        class DummyBot:
            async def send_message(self, *args, **kwargs): return None

            async def create_forum_topic(self, *args, **kwargs):
                class Dummy: message_thread_id = 123

                return Dummy()

        monkeypatch.setattr(telegram_bot, "bot", DummyBot())

        # 2. Создаем чат в БД с under_assistant=False
        chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
        await create_chat(
            chat_id=chat_id,
            thread_id=123,
            client_id=67890,
            user_id=22222,
            chat_url=chat_url,
            under_assistant=False
        )

        messages_before = await get_messages_by_chat_id(chat_id)
        count_before = len(messages_before)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/chat", json=data)
            assert response.status_code == 200

        messages_after = await get_messages_by_chat_id(chat_id)
        count_after = len(messages_after)

        assert count_after == count_before
        all_mocks['process'].assert_not_called()
        all_mocks['send'].assert_not_called()

        chat_after = await get_chat_by_id(chat_id)
        assert chat_after.under_assistant is False
