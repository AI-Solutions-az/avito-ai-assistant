from app.services.openai_assistant import assistant_manager
from app.services.logs import logger

# Асинхронная генерация ответа на сообщение клиента
async def process_message(client_id: str, user_id: str, chat_id: str, message: str, ad_url: str, client_name: str, chat_url: str):
    """
    Process a client message using the OpenAI Assistant API.
    This function now delegates to the AssistantManager.
    """
    return await assistant_manager.process_message(
        client_id=client_id,
        user_id=user_id,
        chat_id=chat_id,
        message=message,
        ad_url=ad_url,
        client_name=client_name,
        chat_url=chat_url
    )