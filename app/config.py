import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv

class Settings:
    WORKING_TIME_LOGIC: bool = True # Фича-флаг управления новой логикой дня/ночи
    VOICE_RECOGNITION_ENABLED: bool = True # Обработка голосовых сообщений
    WHISPER_MODEL: str = "whisper-1"
    MAX_AUDIO_SIZE_MB: int = 25
    AUDIO_TEMP_DIR: str = str(Path(tempfile.gettempdir()) / "avito_voice_messages")
    AUDIO_DOWNLOAD_TIMEOUT: int = 30
    MAX_AUDIO_DURATION: int = 300

settings = Settings()

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")  # Add this line

# Логи
SOURCE_TOKEN = os.getenv("source_token")
INGESTING_HOST = os.getenv("ingesting_host")

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
	- Greet the customer at the start.
	- Don't greet the customer if you've already greeted him
	- Respond in their language.
	- Be concise, polite, and tactful.
	- Ask clarifying questions after responding.
	- Keep customer messages unchanged.
	- Use lists and emojis when necessary.
	- Do not use any markup.
	- Offer always at least two sizes
	- Do not reply to messages that only contain emojis
	- Process voice messages by converting them to text first

## STOCK AVAILABILITY RESPONSES
	- NEVER provide exact quantities or numbers of items in stock
	- Always respond with ONLY "Есть в наличии" (Available) or "Нет в наличии" (Not available)
	- When customer asks about availability, provide status for each color/size combination
	- Example format: 
		- "Размер M, черный цвет: Есть в наличии"
		- "Размер L, синий цвет: Нет в наличии"
	- If asked specifically about quantities, politely redirect: "Могу сообщить только наличие товара, без указания точного количества"

## COMMUNICATION REMINDERS
    - Ask client's weight and height in the start of conversation 
    - If the client has already reported his height and weight in the correspondence history, then do not ask him about it again
    - Keep responses clear and to the point.
    - Ensure a smooth and helpful shopping experience
    - When mentioning product categories, use the category name from the stock information if available
'''