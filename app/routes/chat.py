from datetime import datetime, time
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from app.models.schemas import WebhookRequest
from app.services.avito_api import send_message, get_ad, get_user_info
from app.services.gpt import process_message
from app.services.telegram_notifier import send_alert
from app.services.logs import logger
from app.config import Settings
from db.chat_crud import get_chat_by_id, create_chat, update_chat
from app.services.telegram_notifier import create_telegram_forum_topic
from db.messages_crud import get_latest_message_by_chat_id

# 🎙️ Импорты для голосовых сообщений
from app.services.voice_recognition import voice_recognition
from app.models.voice_schemas import VoiceProcessingStatus

import asyncio

router = APIRouter()

# Очередь сообщений и задачи ожидания
message_queues = {}
processing_tasks = {}


async def message_collector(chat_id, message: WebhookRequest):
    """ Добавляет сообщение в очередь и сбрасывает таймер ожидания """
    
   # 🎙️ ОПРЕДЕЛЯЕМ ТИП СООБЩЕНИЯ И ПОЛУЧАЕМ ТЕКСТ
    if message.is_voice_message():
        logger.info(f"[VoiceMessage] Получено голосовое сообщение в чате {chat_id}")
        
        # Проверяем включен ли модуль голосовых сообщений
        if not voice_recognition.is_voice_recognition_enabled():
            logger.info(f"[VoiceMessage] Голосовые сообщения отключены, пропускаем")
            return None

        # Получаем необходимые данные для обработки
        voice_id = message.get_voice_id()  # Получаем voice_id
        message_id = message.payload.value.id
        user_id = message.payload.value.user_id

        if not voice_id:
            logger.error(f"[VoiceMessage] Не удалось получить voice_id из сообщения")
            await send_message(user_id, chat_id,
                               "Извините, произошла ошибка при обработке голосового сообщения. Попробуйте отправить текст.")
            return None

        try:
            # Распознаем голосовое сообщение
            voice_result = await voice_recognition.process_voice_message(
                voice_url=voice_id,  # Передаем voice_id как voice_url
                chat_id=chat_id,
                message_id=message_id,
                user_id=user_id  # Добавляем user_id
            )

            if voice_result.status == VoiceProcessingStatus.COMPLETED and voice_result.transcribed_text:
                # Успешно распознали - используем как текст
                message_text = voice_result.transcribed_text
                logger.info(f"[VoiceMessage] ✅ Голос распознан за {voice_result.processing_time:.2f}с: '{message_text[:50]}...'")
            else:
                # Ошибка распознавания
                error_msg = voice_result.error_message or "Неизвестная ошибка"
                logger.error(f"[VoiceMessage] ❌ Ошибка распознавания голоса: {error_msg}")
                
                await send_message(user_id, chat_id,
                                   "Извините, не удалось распознать ваше голосовое сообщение. Пожалуйста, отправьте текстовое сообщение.")
                
                # Безопасная отправка Telegram уведомления
                try:
                    await send_alert(f"❌ Ошибка распознавания голосового сообщения: {error_msg}", 0)
                except Exception as telegram_error:
                    logger.error(f"[VoiceMessage] Ошибка отправки Telegram уведомления: {telegram_error}")
                
                return None

        except Exception as e:
            logger.error(f"[VoiceMessage] 💥 Критическая ошибка обработки голоса: {e}")
            await send_message(user_id, chat_id,
                               "Извините, произошла ошибка при обработке голосового сообщения. Попробуйте отправить текст.")
            
            # Безопасная отправка Telegram уведомления
            try:
                await send_alert(f"💥 Критическая ошибка голосового модуля: {str(e)}", 0)
            except Exception as telegram_error:
                logger.error(f"[VoiceMessage] Ошибка отправки Telegram уведомления: {telegram_error}")
            
            return None
            
    elif message.is_text_message():
        # Обычное текстовое сообщение
        message_text = message.payload.value.content.text
    else:
        # Неподдерживаемый тип сообщения
        logger.warning(f"[Message] Неподдерживаемый тип сообщения: {message.payload.value.type}")
        return None

    # 📝 ВСЯ ОСТАЛЬНАЯ ЛОГИКА ОСТАЕТСЯ БЕЗ ИЗМЕНЕНИЙ
    user_id = message.payload.value.user_id
    author_id = message.payload.value.author_id
    item_id = message.payload.value.item_id
    
    if str(message.payload.value.author_id) == "0":
        logger.info(f"Пропуск системного сообщения...")
        return None

    # Создание ссылки на чат
    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'

    # Получение ссылки на объявление, по которому было сообщение
    ad_url = await get_ad(user_id, item_id)

    # Получение информации по пользователю
    user_name, user_url = await get_user_info(user_id, chat_id)
    current_time = datetime.now().time()
    is_night_time = time(22, 0) <= current_time or current_time <= time(10, 0)

    # Проверка существования чата в БД AIvito
    if not await get_chat_by_id(chat_id):
        logger.info(f"[Logic] Чат {chat_id} отсутствует")
        thread_id = await create_telegram_forum_topic(f'{user_name}, {item_id}')
        await create_chat(chat_id, thread_id, author_id, user_id, chat_url, under_assistant=is_night_time)
        await send_alert(f"Создан новый чат\nКлиент: {user_name}\nСсылка на клиента: {user_url}\n"
                         f"Объявление: {ad_url}\nСссылка на чат: {chat_url}\n", thread_id)
        logger.info(f"[Logic] Создан новый чат {chat_id}")

    chat_object = await get_chat_by_id(chat_id)

    if chat_object.under_assistant is False:
        logger.info(f'[Logic] Чат бот отключен в чате {chat_id} для юзера {user_id}')
        return None

    if Settings.WORKING_TIME_LOGIC:
        # Дневной режим (10:00 - 22:00)
        if not is_night_time:
            # Если сообщение от менеджера - ставим метку
            if str(author_id) == str(user_id):
                await update_chat(
                    chat_id=chat_id,
                    under_assistant=False  # Менеджер работает самостоятельно
                )
                logger.info(f"[Logic] Менеджер активен в чате {chat_id}")
            logger.info(f"[Logic] Получено сообщение от пользователя в нерабочее время {chat_id}")
            return None  # Бот не обрабатывает сообщения днем

        # Ночной режим (22:00 - 10:00)
        else:
            # Создание/обновление чата в БД (обязательно для всех сообщений)
            if user_id == author_id:
                last_message = await get_latest_message_by_chat_id(chat_id)
                if last_message == message_text:
                    logger.info(f'[Logic] Хук на собственное сообщение в чате {chat_id}')
                else:
                    await update_chat(chat_id=chat_id, under_assistant=False)
                    await send_alert("❗️К чату подключился оператор", chat_object.thread_id)
                    logger.info(f'[Logic] К чату {chat_id} подключился оператор')
                return None

    if user_id == author_id:
        last_message = await get_latest_message_by_chat_id(chat_id)
        if last_message == message_text:
            logger.info(f'[Logic] Хук на собственное сообщение в чате {chat_id}')
        else:
            await update_chat(chat_id=chat_id, under_assistant=False)
            await send_alert("❗️К чату подключился оператор", chat_object.thread_id)
            logger.info(f'[Logic] К чату {chat_id} подключился оператор')
        return None

    # Проверка тут, так как нельзя ставить очередь на собственное сообщение
    if chat_id not in message_queues:
        message_queues[chat_id] = asyncio.Queue()

    queue = message_queues[chat_id]
    
    # 🎙️ Создаем объект сообщения с распознанным текстом для голосовых
    message_for_queue = message
    if message.is_voice_message():
        # Создаем копию сообщения с замененным текстом
        message_for_queue.payload.value.content.text = message_text
        
    await queue.put(message_for_queue)

    # Сбрасываем существующую задачу ожидания, если она есть
    if chat_id in processing_tasks and not processing_tasks[chat_id].done():
        processing_tasks[chat_id].cancel()

    # Запускаем новый таймер
    processing_tasks[chat_id] = asyncio.create_task(process_queue_after_delay(chat_id, author_id, user_id, message_text, ad_url, user_name, chat_object.thread_id))


async def process_queue_after_delay(chat_id, author_id, user_id, message_text, ad_url, user_name, thread_id):
    """ Ждет 20 секунд без новых сообщений, затем обрабатывает очередь """
    try:
        logger.info(f"[Queue] Ожидание 20 секунд для {chat_id}")
        await asyncio.sleep(20)  # Ожидание без сброса
    except asyncio.CancelledError:
        return  # Таймер был сброшен новым сообщением

    queue = message_queues.get(chat_id)
    if not queue:
        return

    messages = []
    while not queue.empty():
        messages.append(await queue.get())

    # Склеиваем все сообщения (теперь голосовые уже содержат распознанный текст)
    combined_message = " ".join(msg.payload.value.content.text for msg in messages)

    # Отправляем на обработку
    await process_and_send_response(combined_message, chat_id, author_id, user_id, ad_url, user_name, thread_id)


async def process_and_send_response(combined_message, chat_id, author_id, user_id, ad_url, user_name, thread_id):
    """ Обрабатывает сообщение и отправляет ответ """
    logger.info(f'[Logic] Обработка запроса от {chat_id}')

    chat_url = f'https://www.avito.ru/profile/messenger/channel/{chat_id}'
    response = await process_message(client_id=author_id, user_id=user_id, chat_id=chat_id, message=combined_message, ad_url=ad_url, client_name=user_name, chat_url=chat_url)

    if response == "__emoji_only__":
        logger.info(f"[Logic] Пропущено сообщение только из эмодзи в чате {chat_id}")
    elif response is None:
        logger.error(f'[Logic] Не получен ответ от модели в чате {chat_id}')
    else:
        logger.info(f"[Logic] Чат {chat_id}\n"
                    f"Ответ модели: {response}")
        await send_message(user_id, chat_id, response)
        await send_alert(f"💁‍♂️ {user_name}: {combined_message}\n🤖 Бот: {response}\n_____\n\n",
                         thread_id=thread_id)


@router.post("/chat")
async def chat(message: WebhookRequest, background_tasks: BackgroundTasks):
    """ Принимает сообщение и добавляет его в очередь обработки """
    chat_id = message.payload.value.chat_id
    
    # 🔍 ОТЛАДОЧНОЕ ЛОГИРОВАНИЕ - ВРЕМЕННО ДЛЯ АНАЛИЗА СТРУКТУРЫ
    message_type = message.payload.value.type
    logger.info(f"[DEBUG] Тип сообщения: {message_type}")
    logger.info(f"[DEBUG] Полная структура content: {message.payload.value.content}")
    
    if message_type == "voice":
        logger.info(f"[DEBUG] Это голосовое сообщение!")
        logger.info(f"[DEBUG] content.text: {getattr(message.payload.value.content, 'text', 'НЕТ')}")
        logger.info(f"[DEBUG] content.url: {getattr(message.payload.value.content, 'url', 'НЕТ')}")
        logger.info(f"[DEBUG] content.voice: {getattr(message.payload.value.content, 'voice', 'НЕТ')}")
        logger.info(f"[DEBUG] Вызов is_voice_message(): {message.is_voice_message()}")
        logger.info(f"[DEBUG] Вызов get_voice_url(): {message.get_voice_url()}")
    
    # Логируем тип входящего сообщения
    if message.is_voice_message():
        voice_url = message.get_voice_url()
        duration = message.get_voice_duration()
        duration_str = f" ({duration}с)" if duration else ""
        logger.info(f"[Webhook] Получено голосовое сообщение{duration_str} в чате {chat_id}: {voice_url}")
    elif message.is_text_message():
        text_preview = message.get_message_text()[:50] + "..." if len(
            message.get_message_text() or "") > 50 else message.get_message_text()
        logger.info(f"[Webhook] Получено текстовое сообщение в чате {chat_id}: '{text_preview}'")
    else:
        logger.warning(f"[Webhook] Получено сообщение неизвестного типа '{message_type}' в чате {chat_id}")

    background_tasks.add_task(message_collector, chat_id, message)
    return JSONResponse(content={"ok": True}, status_code=200)

