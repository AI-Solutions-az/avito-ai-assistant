import json
from app.config import OPENAI_API_KEY, OPENAI_ASSISTANT_ID, prompt
from app.services.logs import logger
from openai import OpenAI
from db.messages_crud import create_message
from db.escalation_crud import create_escalation
from db.returns_crud import create_return
from db.orders_crud import create_order


class AssistantManager:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.assistant_id = OPENAI_ASSISTANT_ID

    async def create_assistant(self):
        """
        Create a new OpenAI Assistant if OPENAI_ASSISTANT_ID is not provided.
        This should be run once during setup, not on every request.
        """
        if not self.assistant_id:
            logger.info("[Assistant] Creating new assistant")

            assistant = self.client.beta.assistants.create(
                name="Avito Sales Assistant",
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
                model="gpt-4o-mini"  # You can adjust this to the model you want
            )

            logger.info(f"[Assistant] Assistant created with ID: {assistant.id}")
            self.assistant_id = assistant.id
            return assistant.id

        return self.assistant_id

    async def get_or_create_thread(self, chat_id):
        """
        Get an existing thread ID from the database or create a new one.
        We'll use the chat_id from Avito as the external identifier.
        """
        try:
            # First, check if we have a thread ID stored in the database
            from db.chat_crud import get_chat_by_id, update_chat

            chat_object = await get_chat_by_id(chat_id)

            if chat_object and hasattr(chat_object, 'thread_id_openai') and chat_object.thread_id_openai:
                # Check if the thread_id_openai is an OpenAI thread ID (starts with 'thread_')
                if isinstance(chat_object.thread_id_openai, str) and chat_object.thread_id_openai.startswith('thread_'):
                    logger.info(f"[Assistant] Using existing OpenAI thread: {chat_object.thread_id_openai}")
                    return chat_object.thread_id_openai

            # If no valid thread_id_openai, create a new one
            thread = self.client.beta.threads.create()
            logger.info(f"[Assistant] Created new OpenAI thread: {thread.id}")

            # Update the chat in the database with the new OpenAI thread ID
            if chat_object:
                await update_chat(chat_id=chat_id, thread_id_openai=thread.id)
                logger.info(f"[Assistant] Updated chat {chat_id} with OpenAI thread {thread.id}")

            return thread.id

        except Exception as e:
            logger.error(f"[Assistant] Error getting/creating thread: {e}")
            # Create a new thread if there's an error
            thread = self.client.beta.threads.create()
            logger.info(f"[Assistant] Created new OpenAI thread: {thread.id}")
            return thread.id

    async def process_message(self, client_id, user_id, chat_id, message, ad_url, client_name, chat_url):
        """
        Process a message using the Assistants API.
        This replaces the old process_message function.
        """
        logger.info(f"[Assistant] Processing message in chat {chat_id}")

        # Add message to database for record-keeping
        await create_message(chat_id, client_id, from_assistant=False, message=message)

        try:
            # Get or create a thread for this chat
            thread_id = await self.get_or_create_thread(chat_id)

            # Get stock information
            from app.services.google_sheets_api import fetch_google_sheet_stock, get_knowledge_base

            # Retrieve stock information
            logger.info(f"[Assistant] Getting stock info for {ad_url}")
            stock_data = await fetch_google_sheet_stock(ad_url)

            if not stock_data:
                logger.warning(f"[Assistant] No stock data found for {ad_url}")
                return None

            # Get knowledge base
            logger.info(f"[Assistant] Getting knowledge base")
            # knowledge_base = await get_knowledge_base() # Комментируем, чтобы было сэкономить токены

            # Add context as a system message
            # Note: With Assistants API we use a new message for the context to ensure it's used
            context_message = f"""
            # STOCK AVAILABILITY AND INFORMATION: {stock_data}
            # COMMON QUESTIONS ARE PRESENTED IN knowledge_base.docs FILE
            """

            # Add the context message to the thread
            self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=context_message
            )

            # Add the user message to the thread
            self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=message
            )

            # Run the assistant
            run = self.client.beta.threads.runs.create_and_poll(
                thread_id=thread_id,
                assistant_id=self.assistant_id
            )

            # Handle tool calls/function calls if any
            if run.required_action:
                tool_outputs = []

                for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                    function_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)

                    # Handle escalation
                    if function_name == "escalation":
                        reason = arguments.get("reason")

                        # Create an escalation in the database
                        await create_escalation(chat_id, client_id, client_name, chat_url, reason)

                        # Get the Telegram thread_id from the chat object
                        from db.chat_crud import get_chat_by_id
                        chat_object = await get_chat_by_id(chat_id)
                        telegram_thread_id = chat_object.thread_id if chat_object else 0

                        # Notify via Telegram
                        from app.services.telegram_notifier import send_alert
                        await send_alert(f"❗️Требуется срочное внимание менеджера\n\n"
                                         f"Товар: {ad_url}\n"
                                         f"Причина: {reason}\n"
                                         f"Ссылка на чат: {chat_url}", thread_id=telegram_thread_id)

                        # Add the tool output
                        tool_outputs.append({
                            "tool_call_id": tool_call.id,
                            "output": json.dumps({"status": "success", "message": "Escalation created"})
                        })

                    # Handle create order
                    elif function_name == "create_order":
                        size = arguments.get("size")
                        color = arguments.get("color")

                        # Get good_name from stock data
                        stock = json.loads(stock_data)
                        good_name = stock.get('name')

                        # Create an order in the database
                        await create_order(chat_id, client_id, client_name, color, size, ad_url, good_name)

                        # Notify via Telegram
                        from app.services.telegram_notifier import send_alert
                        await send_alert(f"Новый заказ\n\n"
                                         f"Товар: {ad_url}\n"
                                         f"Размер: {size}\n"
                                         f"Цвет: {color}", thread_id=138)

                        # Add the tool output
                        tool_outputs.append({
                            "tool_call_id": tool_call.id,
                            "output": json.dumps({"status": "success", "message": "Order created"})
                        })

                    # Handle initiate return
                    elif function_name == "initiate_return":
                        date_of_order = arguments.get("date_of_order")
                        reason = arguments.get("reason")

                        # Create a return in the database
                        await create_return(chat_id, client_id, client_name, reason, ad_url)

                        # Notify via Telegram
                        from app.services.telegram_notifier import send_alert
                        await send_alert(f"Новая заявка на возврат\n\n"
                                         f"Товар: {ad_url}\n"
                                         f"Заказ от: {date_of_order}\n"
                                         f"Причина: {reason}", thread_id=76)

                        # Add the tool output
                        tool_outputs.append({
                            "tool_call_id": tool_call.id,
                            "output": json.dumps({"status": "success", "message": "Return initiated"})
                        })

                # Submit the tool outputs and wait for completion
                if tool_outputs:
                    run = self.client.beta.threads.runs.submit_tool_outputs_and_poll(
                        thread_id=thread_id,
                        run_id=run.id,
                        tool_outputs=tool_outputs
                    )

            # Get the messages after the run is complete
            messages = self.client.beta.threads.messages.list(
                thread_id=thread_id
            )

            # Get the last assistant message
            assistant_messages = [
                msg for msg in messages.data
                if msg.role == "assistant"
            ]

            if not assistant_messages:
                logger.error(f"[Assistant] No assistant messages found in thread {thread_id}")
                return None

            # Get the most recent assistant message
            last_assistant_message = assistant_messages[0]
            reply = last_assistant_message.content[0].text.value if last_assistant_message.content else ""

            # Save the response to the database
            await create_message(chat_id, user_id, from_assistant=True, message=reply)

            logger.info(f"[Assistant] Response: {reply}")
            return reply

        except Exception as e:
            logger.error(f"[Assistant] Error processing message: {e}")
            return None


# Create a singleton instance
assistant_manager = AssistantManager()