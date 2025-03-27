import json
import httpx
from app.redis_db import save_message, get_history
from app.config import prompt
from app.services.google_sheets_api import fetch_google_sheet_stock, get_knowledge_base
from app.services.telegram_bot import send_alert
from app.config import OPENAI_API_KEY
from app.services.logs import logger
from openai import OpenAI

client = OpenAI(api_key=OPENAI_API_KEY)


# Асинхронная генерация ответа на сообщение клиента
async def process_message(user_id: str, chat_id: str, message: str, ad_url: str):
    logger.info('3. Генерация ответа на сообщение пользователя')
    logger.info(f"3.1. Получено сообщение от пользователя {user_id}: {message}")
    logger.info("3.2. Получение информации по объявлению из базы знаний")

    # Асинхронный вызов для получения информации об объявлении
    stock = await fetch_google_sheet_stock(ad_url)

    # Выключаем бота, если не нашли объявление в базе знаний и отправляем уведомление об этом
    if not stock:
        logger.warning("3.2.1. Объявление не найдено в базе знаний")
        return None

    # Асинхронное получение базы знаний
    logger.info("3.3. Получение информации по кейсам из базы знаний")
    knowledge_base = await get_knowledge_base()

    # Добавление сообщения от пользователя в историю
    await save_message(user_id, chat_id, "user", message)

    # Получение истории сообщений вместе с новым сообщением
    history = await get_history(user_id, chat_id)

    # Инструкция бота
    instructions = {
        "role": "developer",
        "content": f"{prompt}\n# INFORMATION: {stock}# COMMON QUESTIONS: {knowledge_base}History of chat, where messages from developer are your previous messages:"
    }

    messages = [instructions] + history

    logger.info("3.4. Отправка запроса в ChatGPT")

    # Асинхронный запрос к ChatGPT
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": "gpt-4o-mini",
                "messages": messages,
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "initiate_return",
                            "description": "Get reason of return and order date",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "date_of_order": {"type": "string", "description": "Date when order is done"},
                                    "reason": {"type": "string",
                                               "description": "Reason why client want to return the good"}
                                },
                                "required": ["date_of_order", "reason"]
                            }
                        }
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "create_order",
                            "description": "Get size, color of good",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "size": {"type": "string", "description": "Size of the good"},
                                    "color": {"type": "string", "description": "Color of the good"}
                                },
                                "required": ["size", "color"]
                            }
                        }
                    }
                ],
                "tool_choice": "auto"
            }
        )

        finish_reason = response.json()['choices'][0]['finish_reason']

        # Проверка был ли вызов инструмента
        if finish_reason == 'tool_calls':
            logger.info("3.5. Произошел вызов инструмента")
            tool_call = response.json()['choices'][0]['message']['tool_calls'][0]
            name = tool_call['function']['name']

            if name == 'initiate_return':
                logger.info("3.6. Произошел вызов инструмента ВОЗВРАТА")
                arguments = json.loads(tool_call['function']['arguments'])
                date_of_order = arguments.get("date_of_order")
                reason = arguments.get("reason")

                # Оформление возврата и оповещение менеджера
                await send_alert(f"Новая заявка на возврат\n\n"
                                 f"Товар: {ad_url}\n"
                                 f"Заказ от: {date_of_order}\n"
                                 f"Причина: {reason}", thread_id=76)

                # Генерация ответа пользователю
                instructions = {
                    "role": "developer",
                    "content": f'Сообщи о том, что возврат оформлен на заказа от {date_of_order} по причине {reason}'
                }

                messages = [instructions] + history

                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={"model": "gpt-4o-mini", "messages": messages}
                )
                reply = response.json()['choices'][0]['message']['content']
                logger.info("3.7. Сохранение ответа модели в истории редис после ВОЗВРАТА")
                await save_message(user_id, chat_id, "developer", reply)

                return reply

            if name == 'create_order':
                logger.info("3.6. Произошел вызов инструмента СОЗДАТЬ ЗАКАЗ")
                arguments = json.loads(tool_call['function']['arguments'])
                size = arguments.get("size")
                color = arguments.get("color")

                # Оформление возврата и оповещение менеджера
                await send_alert(f"Новый заказ\n\n"
                                 f"Товар: {ad_url}\n"
                                 f"Размер: {size}\n"
                                 f"Цвет: {color}", thread_id=75)

                # Генерация ответа пользователю
                instructions = {
                    "role": "developer",
                    "content": f'Поблагодари клиента за заказ и сообщи, что оформить заказ можно по этому объявлению с указанием доступных способов доставки'
                }

                messages = [instructions] + history

                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={"model": "gpt-4o-mini", "messages": messages}
                )
                reply = response.json()['choices'][0]['message']['content']
                logger.info("3.8. Сохранение ответа модели в истории редис после СОЗДАТЬ ЗАКАЗ")
                await save_message(user_id, chat_id, "developer", reply)

                return reply

        reply = response.json()['choices'][0]['message']['content']
        logger.info("3.9. Сохранение истории в редис обычного сообщения")
        await save_message(user_id, chat_id, "developer", reply)

        # Ответ если не было вызова инструмента
        return reply