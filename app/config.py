import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET=os.getenv("CLIENT_SECRET")


prompt = '''
#GENERAL INFORMATION
Your role is a sales manager at the company.

#GOALS AND TASKS
Your goal is to provide information to customers.
After responding, ask clarifying questions.

#GREETING
Always greet the customer at the beginning of the conversation.

#RESPONSE LANGUAGE
Respond in the customer’s language.

#RESPONSE STYLE
Be concise, but tactful and polite.
Do not rephrase the information provided by the customer.
If the response involves listing information, present it in list format.

#STOCK AVAILABILITY
Help customers choose products based on stock availability.
Stock:
'''

warehouse ={
  "items": [
    {
      "model": "Зип Худи Polo Ralph Зеленый",
      "sizes": {"2ХЛ": 2, "3ХЛ": 1},
      "fit": "Маломерит"
    },
    {
      "model": "Зип Худи Polo Ralph Белая",
      "sizes": {"L": 2, "ХL": 1, "2ХL": 6, "3ХL": 11},
      "fit": "Маломерит"
    },
    {
      "model": "Штаны Nike AСG",
      "sizes": {"С": 2},
      "fit": "Маломерит"
    },
    {
      "model": "Штаны Nike Белые",
      "sizes": {"S": 3, "L": 1},
      "fit": "Маломерит"
    },
    {
      "model": "Штаны Nike Чер-Бел",
      "sizes": {"S": 6, "M": 3, "L": 2},
      "fit": "В размер"
    },
    {
      "model": "Худи Stussy",
      "sizes": {"3ХЛ": 2},
      "fit": "В размер"
    },
    {
      "model": "Зип Худи Polo Ralph Черный",
      "sizes": {"M": 1},
      "fit": "В размер"
    },
    {
      "model": "Зип Худи Polo Ralph Белый",
      "sizes": {"XL": 1},
      "fit": "В размер"
    },
    {
      "model": "Жилетки Nike ACG",
      "sizes": {"2XL": 1},
      "fit": "В размер"
    },
    {
      "model": "Ветровка Polo Ralph Ретро Черный",
      "sizes": {"S": 1, "M": 1},
      "fit": "Маломерит"
    },
    {
      "model": "Ветровка Polo Ralph Ретро Синий",
      "sizes": {"S": 1, "M": 2, "L": 2, "XL": 0},
      "fit": "Маломерит"
    },
    {
      "model": "Ветровка Polo Ralph Ретро Горчичный",
      "sizes": {"XL": 1},
      "fit": "Маломерит"
    },
    {
      "model": "Ветровка Polo Ralph Черный",
      "sizes": {"L": 1, "2Xl": 3, "3XL": 3, "4XL": 4},
      "fit": "Маломерит 2 размера"
    },
    {
      "model": "Ветровка Polo Ralph Синий",
      "sizes": {"L": 2, "XL": 1, "2XL": 3, "3XL": 2, "4XL": 3},
      "fit": "Маломерит 2 размера"
    },
    {
      "model": "Ветровка Polo Ralph Хаки",
      "sizes": {"4XL": 1},
      "fit": "Маломерит 2 размера"
    },
    {
      "model": "Куртка Burberry Хаки",
      "sizes": {"3ХЛ": 1},
      "fit": "Маломерит"
    },
    {
      "model": "Куртка Polo Ralph Серая",
      "sizes": {"2XL": 2},
      "fit": "В размер"
    },
    {
      "model": "Жилетка Polo Ralph Капюшон Черный",
      "sizes": {"XL": 3, "2XL": 1, "3XL": 2, "4XL": "?"},
      "fit": "Маломерит 2 размера"
    },
    {
      "model": "Жилетка Polo Ralph Капюшон Синий",
      "sizes": {"L": 2, "XL": 2, "2XL": 1, "3XL": 3, "4XL": 2},
      "fit": "Маломерит 2 размера"
    }
  ]
}