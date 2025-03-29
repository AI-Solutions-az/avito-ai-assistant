import json
import httpx
from app.redis_db import save_message, get_history
from app.config import prompt
from app.services.google_sheets_api import fetch_google_sheet_stock, get_knowledge_base
from app.services.telegram_notifier import send_alert
from app.config import OPENAI_API_KEY
from app.services.logs import logger
from openai import OpenAI
from db.returns_crud import create_return
from db.orders_crud import create_order
from db.messages_crud import create_message
from db.escalation_crud import create_escalation

client = OpenAI(api_key=OPENAI_API_KEY)


# Асинхронная генерация ответа на сообщение клиента
async def process_message(client_id: str, user_id:str, chat_id: str, message: str, ad_url: str, client_name:str, chat_url:str):
    logger.info(f"[Logic] Старт обработки сообщения в чате {chat_id}")
    # Получение информации об объявлении
    logger.info(f"[Logic] Получение информации по url {ad_url}")
    data = await fetch_google_sheet_stock(ad_url)

    # Выключаем бота, если не нашли объявление в базе знаний и отправляем уведомление об этом
    if not data:
        logger.warning(f"[Logic] Объявление не найдено в базе знаний {chat_id}")
        return None

    # Получение наименования позиции
    stock = json.loads(data)

    # Получаем имя товара
    good_name = stock.get('name')

    # Асинхронное получение базы знаний
    logger.info(f"[Logic] Получение информации по кейсам из базы знаний для {chat_id}")
    knowledge_base = await get_knowledge_base()

    # Добавление сообщения от пользователя в историю
    await save_message(client_id, chat_id, "user", message)
    # Добавление сообщения от пользователя в БД
    await create_message(chat_id, client_id, from_assistant=False, message=message)

    # Получение истории сообщений вместе с новым сообщением
    history = await get_history(client_id, chat_id)

    # Инструкция бота
    instructions = {
        "role": "developer",
        "content": f"{prompt}\n"
                   f"# INFORMATION: {stock}\n"
                   f"# COMMON QUESTIONS: {knowledge_base}\n"
                   f"History of chat, where messages from developer are your previous messages:"
    }

    messages = [instructions] + history

    logger.info(f"[Logic] Отправка запроса в ChatGPT для {chat_id}")

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
                            "description": "Get size, color of good and get confirmation that client is ready to place an order",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "size": {"type": "string", "description": "Size of the good"},
                                    "color": {"type": "string", "description": "Color of the good"}
                                },
                                "required": ["size", "color"]
                            }
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "escalation",
                            "description": "Client want to be connected with manager of operator",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "reason": {"type": "string", "description": "Reason of escalation"},
                                },
                                "required": ["reason"]
                            }
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "size_selection",
                            "description": "Client have sent height and weight",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "size": {"type": "string", "description": "appropriate size of the good"},
                                },
                                "required": ["size"]
                            }
                        },
                    }
                ],
                "tool_choice": "auto"
            }
        )

        finish_reason = response.json()['choices'][0]['finish_reason']

        # Проверка был ли вызов инструмента
        if finish_reason == 'tool_calls':
            logger.info(f"[Logic] Произошел вызов инструмента в чате {chat_id}")
            tool_call = response.json()['choices'][0]['message']['tool_calls'][0]
            name = tool_call['function']['name']

            if name == 'size_and_color_selection':
                logger.info(f"[Logic] Инициировано определение подходящего размера в чате {chat_id}")
                arguments = json.loads(tool_call['function']['arguments'])
                size = arguments.get("size")

                # Генерация ответа пользователю
                instructions = {
                    "role": "developer",
                    "content": f"{prompt}\n"
                               f"If size {size} is available on stock, then inform the client about it, indicating the available colors and offering to place an order.\n"
                               f"If there is no size {size}, then select for the client one or several closest sizes available in the warehouse."
                               f"In this case, if the available size is larger than {size}, then highlight to the client that the product will fit loosely, and if the available size is smaller than {size}, then highlight to the client that the product will fit tightly\n"
                               f"# INFORMATION AND STOCK: {stock}\n"
                               f"History of chat, where messages from developer are your previous messages:"
                }
                messages = [instructions] + history

                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={"model": "gpt-4o-mini", "messages": messages}
                )
                reply = response.json()['choices'][0]['message']['content']
                logger.info(f"[Logic] Сохранение ответа модели в истории редис после ВОЗВРАТА для чата {chat_id}")
                await save_message(client_id, chat_id, "developer", reply)
                await create_message(chat_id, user_id, from_assistant=True, message=reply)
                return reply

            if name == 'initiate_return':
                logger.info(f"[Logic] Инициирован возврат в чате {chat_id}")
                arguments = json.loads(tool_call['function']['arguments'])
                date_of_order = arguments.get("date_of_order")
                reason = arguments.get("reason")

                # Оформление возврата и оповещение менеджера
                await send_alert(f"Новая заявка на возврат\n\n"
                                 f"Товар: {ad_url}\n"
                                 f"Заказ от: {date_of_order}\n"
                                 f"Причина: {reason}", thread_id=76) # 76 это номер топика возвратов в ТГ
                # Создание записи в таблице возвратов
                await create_return(chat_id, client_id, client_name, reason, ad_url)
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
                logger.info(f"[Logic] Сохранение ответа модели в истории редис после ВОЗВРАТА для чата {chat_id}")
                await save_message(client_id, chat_id, "developer", reply)
                await create_message(chat_id, user_id, from_assistant=True, message=reply)
                return reply

            if name == 'create_order':
                logger.info(f"[Logic] Произошел вызов инструмента СОЗДАТЬ ЗАКАЗ для чата {chat_id}")
                arguments = json.loads(tool_call['function']['arguments'])
                size = arguments.get("size")
                color = arguments.get("color")

                # Оформление возврата и оповещение менеджера
                await send_alert(f"Новый заказ\n\n"
                                 f"Товар: {ad_url}\n"
                                 f"Размер: {size}\n"
                                 f"Цвет: {color}", thread_id=138)
                # Сохранение создания заказа в БД
                await create_order(chat_id, client_id, client_name, color, size, ad_url, good_name)
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
                logger.info(f"[Logic] Сохранение ответа модели в истории редис после СОЗДАТЬ ЗАКАЗ для чата {chat_id}")
                await save_message(client_id, chat_id, "developer", reply)
                await create_message(chat_id, user_id, from_assistant=True, message=reply)

                return reply

            if name == 'escalation':
                logger.info(f"[Logic] Произошел вызов инструмента ЭСКАЛАЦИЯ для чата {chat_id}")
                arguments = json.loads(tool_call['function']['arguments'])
                reason = arguments.get("reason")

                # Оформление возврата и оповещение менеджера
                await send_alert(f"❗️Требуется срочное внимание менеджера\n\n"
                                 f"Товар: {ad_url}\n"
                                 f"Причина: {reason}\n"
                                 f"Ссылка на чат: {chat_url}", thread_id=0)
                # Сохранение эскалации в БД
                await create_escalation(chat_id, client_id, client_name, chat_url, reason)
                # Генерация ответа пользователю
                instructions = {
                    "role": "developer",
                    "content": f'Сообщи клиенту, что позвал менеджера на помощь'
                }

                messages = [instructions] + history

                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={"model": "gpt-4o-mini", "messages": messages}
                )
                reply = response.json()['choices'][0]['message']['content']
                logger.info(f"[Logic] Сохранение ответа модели в истории редис после СОЗДАТЬ ЗАКАЗ для чата {chat_id}")
                await save_message(client_id, chat_id, "developer", reply)
                await create_message(chat_id, user_id, from_assistant=True, message=reply)

                return reply


        reply = response.json()['choices'][0]['message']['content']
        logger.info(f"[Logic] Сохранение ответа модели в редис для чата {chat_id}")
        await save_message(client_id, chat_id, "developer", reply)
        await create_message(chat_id, user_id, from_assistant=True, message=reply)

        # Ответ если не было вызова инструмента
        return reply