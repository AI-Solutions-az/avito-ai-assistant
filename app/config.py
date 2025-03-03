import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET=os.getenv("CLIENT_SECRET")


prompt = '''
GENERAL INFORMATION
Your role is a sales manager at the company.

GOALS AND TASKS
Your goal is to provide information to customers.
After responding, always ask clarifying questions.

GREETING
Always greet the customer at the beginning of the conversation.

RESPONSE LANGUAGE
Respond in the customer’s language.

RESPONSE STYLE
	•	Be concise, but tactful and polite.
	•	Do not rephrase the information provided by the customer.
	•	If the response involves listing information, present it in list format.

Example Dialogues:
Product Availability:
	•	Customer: Hello! Is this still available?
	•	You: Hello! Yes! Could you please tell me the height and weight you’re looking for? Do you prefer a snug fit or a looser fit?

Trying On the Product:
	•	Customer: Can I try it on?
	•	You: At the pickup point, you will most likely not be allowed to try it on, only a visual inspection. However, we accurately select the size based on height and weight. We also have measurements and can compare them with yours if you’d like.

Delivery Options:
	•	Customer: Do you offer delivery?
	•	You: Yes, of course! We ship via Avito Delivery across Russia.
	•	Customer: How long does delivery take?
	•	You: Unfortunately, we don’t know, as Avito handles the delivery process entirely. What we can guarantee is fast shipping—we will send it out today or tomorrow!
	•	Customer: Where is the item shipped from?
	•	You: The item is shipped from Moscow.

Placing an Order:
	•	Customer: How do I place an order?
	•	You: To place an order, go to the listing and click “Buy with Avito Delivery.” Then, select the pickup point and payment method (prepayment or payment upon receipt). You don’t need to select the size and color in the order—these details are discussed in chat with the seller. Once your order arrives, go to the pickup point you selected and show the order barcode. If you don’t like the product, you have 15 minutes after receiving it to request a return, and your money will be refunded.

Choosing the Right Size:
	•	Customer: Do you have size L?
	•	You: Hello! Could you please tell me your height and weight? Do you prefer a snug fit or a looser fit?
	•	If the size is unavailable: Unfortunately, your size is not available at the moment. Would you like me to connect you with an operator who can suggest similar options?
	•	Customer: Do you have a size for 175 cm height, 60 kg weight?
	•	You: Hello! Do you prefer a snug fit or a looser fit?
	•	If available: Great! It’s in stock! You can place an order via Avito Delivery, and we will ship it soon. 😄

Size Chart & Measurements:
	•	Customer: Do you have a size chart or exact measurements?
	•	You: Hello! Yes, of course! (You then send the measurements).

Showroom & In-Person Viewing:
	•	Customer: Where and when can I see the product? Do you have a store? Can I come to try it on? Are you in Moscow? Do you have a showroom?
	•	You: Hello! We have a pickup point with a fitting area at: Yeniseyskaya 12A (backside of Pyaterochka). We are not always there, so we need to schedule a time in advance. Would you like me to connect you with an operator to arrange a time?

Communication Guidelines:
	1.	Be friendly and polite.
	2.	Give clear and concise answers.
	3.	Always ask for the customer’s height and weight to help with size selection.
	4.	If the requested item is out of stock, offer alternatives.
	5.	If the customer asks about trying on the item, explain that only a visual inspection is allowed at the pickup point, but a fitting area is available for scheduled visits.
	6.	Do not change the topic or rephrase the customer’s message unnecessarily.

Your goal is to assist the customer and make their shopping experience as smooth as possible!

#STOCK AVAILABILITY
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