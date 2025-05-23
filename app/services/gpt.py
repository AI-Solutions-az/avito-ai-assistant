# app/services/gpt.py - Updated version

from app.services.client_openai_assistant import client_assistant_manager  # CHANGED: Use client-specific manager
from app.services.logs import logger

# Updated function signature to include client_avito_id
async def process_message(client_id: str, user_id: str, chat_id: str, message: str,
                         ad_url: str, client_name: str, chat_url: str, client_avito_id: str):
    """
    Process a client message using the client-specific OpenAI Assistant API.
    This function now delegates to the ClientAssistantManager with client identification.
    """
    return await client_assistant_manager.process_message(
        client_id=client_id,
        user_id=user_id,
        chat_id=chat_id,
        message=message,
        ad_url=ad_url,
        client_name=client_name,
        chat_url=chat_url,
        client_avito_id=client_avito_id  # NEW: Pass client identifier
    )