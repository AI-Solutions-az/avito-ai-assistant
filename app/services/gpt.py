import logging
from openai import OpenAI
import os, json
from app.redis_db import save_message, get_history
from dotenv import load_dotenv
from app.config import prompt
from app.services.google_sheets_api import fetch_google_sheet_stock, get_knowledge_base
from app.services.telegram_bot import send_alert

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Настройка логирования
logger = logging.getLogger("uvicorn")

# Генерация ответа на сообщение клиента
def process_message(user_id: str, chat_id:str, message: str, ad_url):
    logger.info(f"3.1. Получено сообщение от пользователя {user_id}: {message}")
    logger.info("3.2. Получение информации по объявлению из базы знаний")
    stock = fetch_google_sheet_stock(ad_url)

    # Выключаем бота, если не нашли объявление в базе знаний и отправляем уведомление об этом
    if not stock:
        # send_alert(f'Невозможно найти объявление {ad_url} в базе знаний')
        logger.warning("3.2.1. Объявление не найдено в базе знаний")
        return None

    # Запрос базы знаний
    logger.info("3.3. Получение информации по кейсам из базы знаний")
    knowledge_base = get_knowledge_base()

    # Добавление сообщения от пользователя в историю
    save_message(user_id, chat_id, "user", message)

    # Получение истории сообщений вместе с новым сообщением
    history = get_history(user_id, chat_id)
    # Инструкция бота
    instructions = {"role": "developer", "content": f"{prompt}\n"
                                                    f"# INFORMATION: {stock}"
                                                    f"# COMMON QUESTIONS: {knowledge_base}"
                                                    f"History of chat, where messages from developer are your previous messages:"}

    messages = [instructions] + history

    logger.info("3.4. Отправка запроса в ChatGPT")
    response = client.chat.completions.create(model="gpt-4o-mini"
                                              , messages=messages
                                              , tools=[
                                                {
                                                  "type": "function",
                                                  "function": {
                                                    "name": "initiate_return",
                                                    "description": "Get reason of return and order date",
                                                    "parameters": {
                                                      "type": "object",
                                                      "properties": {
                                                        "date_of_order": {
                                                          "type": "string",
                                                          "description": "Date when order is done"
                                                        },
                                                        "reason": {
                                                          "type": "string",
                                                          "description": "Reason why client want to return the good"
                                                        }
                                                      },
                                                      "required": ["date_of_order", "reason"]
                                                    }
                                                  }
                                                }]
                                              , tool_choice="auto"
                                              )

    finish_reason = response.choices[0].finish_reason
    # Проверка был ли вызов инструмента
    if finish_reason=='tool_calls':
        logger.info("3.5. Произошел вызов инструмента")
        # Достаем tool_calls
        tool_call = response.choices[0].message.tool_calls[0]
        # Определяем какая функция была вызвана
        name = tool_call.function.name

        if name == 'initiate_return':
            logger.info("3.6. Произошел вызов инструмента ВОЗВРАТА")
            # Парсим JSON аргументы
            arguments = json.loads(tool_call.function.arguments)
            # Извлекаем нужные поля
            date_of_order = arguments.get("date_of_order")
            reason = arguments.get("reason")

            # Оформление возврата и оповещение менеджера
            send_alert(f"Новая заявка на возврат\n\n"
                       f"Заказ от: {date_of_order}\n"
                       f"Причина: {reason}")

            # Генерация ответа пользователю
            instructions = [{"role": "developer"
                                , "content": f'Сообщи о том, что возврат оформлен на заказа от {date_of_order} по причине {reason}'
                             }]

            messages = [instructions] + history

            response = client.chat.completions.create(model="gpt-4o-mini", messages=messages)
            reply = response.choices[0].message.content
            logger.info("3.7. Сохранение истории в редис")
            save_message(user_id, chat_id, "developer", reply)
            return reply

    reply = response.choices[0].message.content
    logger.info("3.8. Сохранение истории в редис")
    save_message(user_id, chat_id, "developer", reply)

    # Ответ если не было вызова инструмента
    return reply