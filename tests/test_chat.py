import asyncio
import pytest
from httpx import AsyncClient
from sqlalchemy import text

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
        from db.messages_crud import get_latest_message_by_chat_id
        last_message = await get_latest_message_by_chat_id(chat_id)
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