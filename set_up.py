# setup_multi_client.py

import asyncio
import os
from db.db_config import engine, Base
from db.client_crud import create_client
from app.services.logs import logger


async def create_tables():
    """Create new database tables"""
    async with engine.begin() as conn:
        # Create the new clients table
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/updated")


async def migrate_existing_config():
    """Migrate existing environment configuration to first client"""
    try:
        # Get existing configuration from environment
        client_id = os.getenv("CLIENT_ID")
        client_secret = os.getenv("CLIENT_SECRET")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        openai_assistant_id = os.getenv("OPENAI_ASSISTANT_ID")
        telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        google_api_key = os.getenv("API_KEY")
        google_spreadsheet_id = os.getenv("SPREADSHEET_ID")
        google_range = os.getenv("RANGE")
        warehouse_sheet_name = os.getenv("WAREHOUSE_SHEET_NAME")
        knowledge_base_sheet_name = os.getenv("KNOWLEDGE_BASE_SHEET_NAME")

        if not client_id or not client_secret:
            logger.warning("No existing CLIENT_ID or CLIENT_SECRET found in environment")
            return

        # Create first client from existing config
        client = await create_client(
            client_name="Default Client (Migrated)",
            avito_client_id=client_id,
            avito_client_secret=client_secret,
            openai_api_key=openai_api_key,
            openai_assistant_id=openai_assistant_id,
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
            google_api_key=google_api_key,
            google_spreadsheet_id=google_spreadsheet_id,
            google_range=google_range,
            warehouse_sheet_name=warehouse_sheet_name,
            knowledge_base_sheet_name=knowledge_base_sheet_name
        )

        if client:
            logger.info(f"Successfully migrated existing config to client ID: {client.id}")
            print(f"✅ Migrated existing configuration to client: {client.client_name}")
        else:
            logger.error("Failed to create client from existing config")

    except Exception as e:
        logger.error(f"Error during migration: {e}")


async def setup_example_client():
    """Create an example second client"""
    try:
        example_client = await create_client(
            client_name="Example Store 2",
            avito_client_id="example_client_id_2",
            avito_client_secret="example_secret_2",
            openai_api_key="sk-example-key",
            telegram_bot_token="example_bot_token",
            telegram_chat_id="example_chat_id",
            google_spreadsheet_id="example_spreadsheet_id",
            google_range="A:Z",
            warehouse_sheet_name="Warehouse",
            knowledge_base_sheet_name="KnowledgeBase"
        )

        if example_client:
            print(f"✅ Created example client: {example_client.client_name}")
            print("   You can update this client with real credentials via the API")

    except Exception as e:
        logger.error(f"Error creating example client: {e}")


def update_requirements():
    """Show additional requirements needed"""
    print("\n📦 Additional Requirements:")
    print("Add this to your requirements.txt:")
    print("cryptography>=41.0.0")
    print("\nThen run: pip install cryptography")


def show_env_setup():
    """Show environment setup instructions"""
    print("\n🔐 Environment Setup:")
    print("Add this to your .env file:")
    print("ENCRYPTION_KEY=<generate_this_key>")
    print("\nGenerate encryption key by running:")
    print("python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")


def show_api_usage():
    """Show how to use the new API endpoints"""
    print("\n🔌 API Usage Examples:")
    print("\n1. Create a new client:")
    print("POST /api/clients")
    print("""{
    "client_name": "Fashion Store Name",
    "avito_client_id": "your_avito_client_id",
    "avito_client_secret": "your_avito_secret",
    "openai_api_key": "sk-your-openai-key",
    "openai_assistant_id": "asst_your_assistant_id",
    "telegram_bot_token": "your_bot_token",
    "telegram_chat_id": "your_chat_id",
    "google_api_key": "your_google_api_key",
    "google_spreadsheet_id": "your_spreadsheet_id",
    "google_range": "A:Z",
    "warehouse_sheet_name": "Warehouse",
    "knowledge_base_sheet_name": "KnowledgeBase"
}""")

    print("\n2. List all clients:")
    print("GET /api/clients")

    print("\n3. Get specific client:")
    print("GET /api/clients/{avito_client_id}")

    print("\n4. Update client:")
    print("PUT /api/clients/{client_id}")


async def main():
    """Main setup function"""
    print("🚀 Setting up Multi-Client Support...")

    # Create tables
    await create_tables()

    # Migrate existing config
    await migrate_existing_config()

    # Create example client
    await setup_example_client()

    # Show additional setup instructions
    update_requirements()
    show_env_setup()
    show_api_usage()

    print("\n✅ Multi-client setup complete!")
    print("\nNext steps:")
    print("1. Install cryptography: pip install cryptography")
    print("2. Generate and add ENCRYPTION_KEY to your .env file")
    print("3. Update your main.py to include client management routes")
    print("4. Test the new API endpoints")
    print("5. Update your webhook logic to handle multiple clients")


if __name__ == "__main__":
    asyncio.run(main())