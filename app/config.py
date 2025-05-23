# app/config.py - Updated version

import os
from dotenv import load_dotenv

load_dotenv()

# Global/System configuration (not client-specific)
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")

# NEW: Encryption key for storing client credentials securely
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

# Logging configuration
SOURCE_TOKEN = os.getenv("source_token")
INGESTING_HOST = os.getenv("ingesting_host")

# DEPRECATED: These are now stored per-client in the database
# Keep them for backward compatibility during migration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Will be migrated to client-specific
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Will be migrated to client-specific
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Will be migrated to client-specific
CLIENT_ID = os.getenv("CLIENT_ID")  # Will be migrated to client-specific
CLIENT_SECRET = os.getenv("CLIENT_SECRET")  # Will be migrated to client-specific
OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")  # Will be migrated to client-specific
RANGE = os.getenv("GOOGLE_RANGE")  # Will be migrated to client-specific
API_KEY = os.getenv("GOOGLE_API_KEY")  # Will be migrated to client-specific
SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID")  # Will be migrated to client-specific
WAREHOUSE_SHEET_NAME = os.getenv("WAREHOUSE_SHEET_NAME")  # Will be migrated to client-specific
KNOWLEDGE_BASE_SHEET_NAME = os.getenv("KNOWLEDGE_BASE_SHEET_NAME")  # Will be migrated to client-specific

# Assistant prompt (shared across all clients)
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
	•	Offer always at least two sizes
	•	Do not reply to messages that only contain emojis

## COMMUNICATION REMINDERS
- Ask client's weight and height in the start of conversation.
- If the client has already reported his height and weight in the correspondence history, then do not ask him about it again
- Keep responses clear and to the point.
- Ensure a smooth and helpful shopping experience
'''