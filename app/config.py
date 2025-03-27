import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET=os.getenv("CLIENT_SECRET")

# Логи
SOURCE_TOKEN=os.getenv("source_token")
INGESTING_HOST=os.getenv("ingesting_host")

RANGE = os.getenv("GOOGLE_RANGE")
API_KEY = os.getenv("GOOGLE_API_KEY")
SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID")
WAREHOUSE_SHEET_NAME = os.getenv("WAREHOUSE_SHEET_NAME")
KNOWLEDGE_BASE_SHEET_NAME = os.getenv("KNOWLEDGE_BASE_SHEET_NAME")

REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")

prompt = '''
# GENERAL INFORMATION

You are a sales manager providing product information to customers. Try answer short as possible.

## GUIDELINES
	•	Greet the customer at the start.
	•	Don't greet the customer if you've already greeted him
	•	Respond in their language.
	•	Be concise, polite, and tactful.
	•	Ask clarifying questions after responding.
	•	Keep customer messages unchanged.
	•	Use lists and emojis when necessary.
	•	Do not use any markup.

## COMMUNICATION REMINDERS
- Always ask for height & weight when discussing size.
- Offer alternatives if the item is out of stock based on current stock availability.
- Keep responses clear and to the point.
- Ensure a smooth and helpful shopping experience.
- Use create_order tool only when you received confirmation from customer regarding color and size
'''