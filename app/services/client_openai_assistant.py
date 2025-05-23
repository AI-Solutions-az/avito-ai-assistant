# app/services/client_openai_assistant.py

import json
from app.services.logs import logger
from openai import OpenAI
from db.messages_crud import create_message
from db.escalation_crud import create_escalation
from db.returns_crud import create_return
from db.orders_crud import create_order
from db.client_crud import get_client_by_avito_id


class ClientAssistantManager:
    def __init__(self):
        self.client_instances = {}  # Store OpenAI clients per client_avito_id
        self.client_configs = {}  # Cache client configurations

    async def get_client_openai(self, client_avito_id: str):
        """Get or create OpenAI client instance for specific client"""
        if client_avito_id in self.client_instances:
            return self.client_instances[client_avito_id]

        # Get client configuration
        client = await get_client_by_avito_id(client_avito_id)
        if not client or not client.openai_api_key:
            logger.error(f"OpenAI configuration missing for client {client_avito_id}")
            return None

        # Create and cache OpenAI client
        openai_client = OpenAI(api_key=client.openai_api_key)
        self.client_instances[client_avito_id] = openai_client
        self.client_configs[client_avito_id] = client

        return openai_client

    async def create_assistant(self, client_avito_id: str):
        """Create a new OpenAI Assistant for a specific client"""
        client = await get_client_by_avito_id(client_avito_id)
        if not client:
            logger.error(f"Client {client_avito_id} not found")
            return None

        if client.openai_assistant_id:
            logger.info(f"Assistant already exists for client {client_avito_id}: {client.openai_assistant_id}")
            return client.openai_assistant_id

        openai_client = await self.get_client_openai(client_avito_id)
        if not openai_client:
            return None

        logger.info(f"Creating new assistant for client {client_avito_id}")

        # Use the same prompt from config.py
        from app.config import prompt

        assistant = openai_client.beta.assistants.create(
            name=f"Avito Sales Assistant - {client.client_name}",
            instructions=prompt,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "escalation",
                        "description": "Client wants to be connected with manager or operator, or assistant cannot help the client",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "reason": {"type": "string", "description": "Reason for escalation"},
                            },
                            "required": ["reason"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "create_order",
                        "description": "Create an order for a product",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "size": {"type": "string", "description": "Size of the product"},
                                "color": {"type": "string", "description": "Color of the product"},
                            },
                            "required": ["size", "color"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "initiate_return",
                        "description": "Initiate a return for a product",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "date_of_order": {"type": "string", "description": "Date of the order"},
                                "reason": {"type": "string", "description": "Reason for return"},
                            },
                            "required": ["date_of_order", "reason"]
                        }
                    }
                }
            ],
            model="gpt-4o-mini"
        )

        logger.info(f"Assistant created for client {client_avito_id} with ID: {assistant.id}")

        # Update client with assistant ID
        from db.client_crud import update_client
        await update_client(client.id, openai_assistant_id=assistant.id)

        return assistant.id

    async def get_or_create_thread(self, chat_id, client_avito_id: str):
        """Get an existing thread ID or create a new one for specific client"""
        try:
            from db.chat_crud import get_chat_by_id, update_chat

            chat_object = await get_chat_by_id(chat_id)

            if chat_object and hasattr(chat_object, 'thread_id_openai') and chat_object.thread_id_openai:
                if isinstance(chat_object.thread_id_openai, str) and chat_object.thread_id_openai.startswith('thread_'):
                    logger.info(
                        f"Using existing OpenAI thread for client {client_avito_id}: {chat_object.thread_id_openai}")
                    return chat_object.thread_id_openai

            # Create new thread using client-specific OpenAI instance
            openai_client = await self.get_client_openai(client_avito_id)
            if not openai_client:
                return None

            thread = openai_client.beta.threads.create()
            logger.info(f"Created new OpenAI thread for client {client_avito_id}: {thread.id}")

            if chat_object:
                await update_chat(chat_id=chat_id, thread_id_openai=thread.id)
                logger.info(f"Updated chat {chat_id} with OpenAI thread {thread.id}")

            return thread.id

        except Exception as e:
            logger.error(f"Error getting/creating thread for client {client_avito_id}: {e}")
            return None

    async def process_message(self, client_id, user_id, chat_id, message, ad_url, client_name, chat_url,
                              client_avito_id: str):
        """Process a message using client-specific Assistants API"""
        logger.info(f"Processing message for client {client_avito_id} in chat {chat_id}")

        # Add message to database
        await create_message(chat_id, client_id, from_assistant=False, message=message)

        try:
            # Get client configuration
            client = await get_client_by_avito_id(client_avito_id)
            if not client:
                logger.error(f"Client {client_avito_id} not found")
                return None

            # Get OpenAI client instance
            openai_client = await self.get_client_openai(client_avito_id)
            if not openai_client:
                return None

            # Ensure assistant exists
            assistant_id = client.openai_assistant_id
            if not assistant_id:
                assistant_id = await self.create_assistant(client_avito_id)
                if not assistant_id:
                    return None

            # Get or create thread
            thread_id = await self.get_or_create_thread(chat_id, client_avito_id)
            if not thread_id:
                return None

            # Get stock information using client-specific Google Sheets
            from app.services.client_google_sheets_api import fetch_google_sheet_stock

            logger.info(f"Getting stock info for client {client_avito_id}, ad: {ad_url}")
            stock_data = await fetch_google_sheet_stock(ad_url, client_avito_id)

            if not stock_data:
                logger.warning(f"No stock data found for client {client_avito_id}, ad: {ad_url}")
                return None

            # Add context message
            context_message = f"""
            # STOCK AVAILABILITY AND INFORMATION: {stock_data}
            # COMMON QUESTIONS ARE PRESENTED IN knowledge_base.docs FILE
            """

            # Add context and user message to thread
            openai_client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=context_message
            )

            openai_client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=message
            )

            # Run the assistant
            run = openai_client.beta.threads.runs.create_and_poll(
                thread_id=thread_id,
                assistant_id=assistant_id
            )

            # Handle tool calls if any
            if run.required_action:
                tool_outputs = []

                for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                    function_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)

                    # Handle escalation
                    if function_name == "escalation":
                        reason = arguments.get("reason")
                        await create_escalation(chat_id, client_id, client_name, chat_url, reason)

                        # Send alert using client-specific Telegram
                        from app.services.client_telegram_notifier import send_client_alert
                        from db.chat_crud import get_chat_by_id
                        chat_object = await get_chat_by_id(chat_id)
                        telegram_thread_id = chat_object.thread_id if chat_object else None

                        await send_client_alert(
                            f"❗️Требуется срочное внимание менеджера\n\n"
                            f"Товар: {ad_url}\n"
                            f"Причина: {reason}\n"
                            f"Ссылка на чат: {chat_url}",
                            client_avito_id,
                            telegram_thread_id
                        )

                        tool_outputs.append({
                            "tool_call_id": tool_call.id,
                            "output": json.dumps({"status": "success", "message": "Escalation created"})
                        })

                    # Handle create order
                    elif function_name == "create_order":
                        size = arguments.get("size")
                        color = arguments.get("color")

                        stock = json.loads(stock_data)
                        good_name = stock.get('name')

                        await create_order(chat_id, client_id, client_name, color, size, ad_url, good_name)

                        # Send alert using client-specific Telegram
                        from app.services.client_telegram_notifier import send_client_alert
                        await send_client_alert(
                            f"Новый заказ\n\n"
                            f"Товар: {ad_url}\n"
                            f"Размер: {size}\n"
                            f"Цвет: {color}",
                            client_avito_id,
                            client.telegram_thread_id  # Use client's order thread
                        )

                        tool_outputs.append({
                            "tool_call_id": tool_call.id,
                            "output": json.dumps({"status": "success", "message": "Order created"})
                        })

                    # Handle initiate return
                    elif function_name == "initiate_return":
                        date_of_order = arguments.get("date_of_order")
                        reason = arguments.get("reason")

                        await create_return(chat_id, client_id, client_name, reason, ad_url)

                        # Send alert using client-specific Telegram
                        from app.services.client_telegram_notifier import send_client_alert
                        await send_client_alert(
                            f"Новая заявка на возврат\n\n"
                            f"Товар: {ad_url}\n"
                            f"Заказ от: {date_of_order}\n"
                            f"Причина: {reason}",
                            client_avito_id,
                            client.telegram_thread_id  # Use client's return thread
                        )

                        tool_outputs.append({
                            "tool_call_id": tool_call.id,
                            "output": json.dumps({"status": "success", "message": "Return initiated"})
                        })

                # Submit tool outputs
                if tool_outputs:
                    run = openai_client.beta.threads.runs.submit_tool_outputs_and_poll(
                        thread_id=thread_id,
                        run_id=run.id,
                        tool_outputs=tool_outputs
                    )

            # Get the assistant's response
            messages = openai_client.beta.threads.messages.list(thread_id=thread_id)
            assistant_messages = [msg for msg in messages.data if msg.role == "assistant"]

            if not assistant_messages:
                logger.error(f"No assistant messages found for client {client_avito_id}")
                return None

            last_assistant_message = assistant_messages[0]
            reply = last_assistant_message.content[0].text.value if last_assistant_message.content else ""

            # Save response to database
            await create_message(chat_id, user_id, from_assistant=True, message=reply)

            logger.info(f"Response for client {client_avito_id}: {reply}")
            return reply

        except Exception as e:
            logger.error(f"Error processing message for client {client_avito_id}: {e}")
            return None


# Create singleton instance
client_assistant_manager = ClientAssistantManager()