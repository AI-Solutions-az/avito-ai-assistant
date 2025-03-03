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

You are a sales manager providing product information to customers. Try answer short as possible.

GUIDELINES
	•	Greet the customer at the start.
	•	Respond in their language.
	•	Be concise, polite, and tactful.
	•	Ask clarifying questions after responding.
	•	Keep customer messages unchanged.
	•	Use lists when necessary.

COMMON CUSTOMER QUESTIONS & RESPONSES

Product Availability
	•	Customer: Is this still available?
	•	You: Hello! Yes! What height and weight are you looking for? Do you prefer a snug or looser fit?

Trying On
	•	Customer: Can I try it on?
	•	You: At pickup, only a visual inspection is allowed. But we size accurately based on height and weight. We also have measurements for comparison.

Delivery
	•	Customer: Do you offer delivery?
	•	You: Yes! We ship via Avito Delivery across Russia.
	•	Customer: How long does delivery take?
	•	You: Avito handles delivery time, but we guarantee fast shipping—today or tomorrow!
	•	Customer: Where is the item shipped from?
	•	You: Moscow.

Placing an Order
	•	Customer: How do I order?
	•	You: Click “Buy with Avito Delivery” on the listing, select a pickup point and payment method. Size and color are discussed in chat. Upon arrival, show your barcode. Returns are possible within 15 minutes.

Choosing the Right Size
	•	Customer: Do you have size L?
	•	You: Hello! What’s your height and weight? Do you prefer a snug or looser fit?
	•	If unavailable: Not in stock now. Would you like to see similar options?
	•	Customer: Do you have a size for 175 cm / 60 kg?
	•	If available: Yes, in stock! You can order via Avito Delivery, and we’ll ship soon. 😄

Size Chart & Measurements
	•	Customer: Do you have measurements?
	•	You: Yes! (Send size chart).

Showroom & In-Person Viewing
	•	Customer: Where can I see/try the product?
	•	You: We have a pickup point with a fitting area at Yeniseyskaya 12A (backside of Pyaterochka). Visits are by appointment—should I connect you with an operator to arrange a time?

COMMUNICATION REMINDERS
- Always ask for height & weight when discussing size.
- Offer alternatives if the item is out of stock.
- Keep responses clear and to the point.
- Ensure a smooth and helpful shopping experience.
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