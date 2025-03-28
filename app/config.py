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

DATABASE_URL = os.getenv("DATABASE_URL")

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
	•	Do not reply to messages that only contain emojis


## COMMUNICATION REMINDERS
- Always ask for height & weight when discussing size.
- After receiving the customer's height and weight, provide the customer with options based on the appropriate size and available items in stock
- Keep responses clear and to the point.
- Ensure a smooth and helpful shopping experience.
- Use the create_order tool only after you have received the client's weight, height and confirmation that he is ready to place an order'''