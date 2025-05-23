# debug_client_setup.py - Run this to diagnose and fix issues

import asyncio
import os
from sqlalchemy.exc import SQLAlchemyError
from app.services.logs import logger


async def check_database_connection():
    """Check if database connection works"""
    try:
        from db.db_config import SessionLocal
        async with SessionLocal() as session:
            result = await session.execute("SELECT 1")
            logger.info("✅ Database connection successful")
            return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False


async def check_clients_table():
    """Check if clients table exists"""
    try:
        from db.db_config import SessionLocal
        async with SessionLocal() as session:
            # Try to query the clients table
            result = await session.execute("SELECT COUNT(*) FROM assistant.clients")
            count = result.scalar()
            logger.info(f"✅ Clients table exists with {count} records")
            return True
    except Exception as e:
        logger.error(f"❌ Clients table issue: {e}")
        return False


async def create_tables_if_missing():
    """Create missing tables"""
    try:
        from db.db_config import engine, Base
        from db.models import Clients  # Import to ensure table is registered

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("✅ Database tables created/updated")
        return True
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        return False


async def test_client_crud():
    """Test client CRUD operations"""
    try:
        from db.client_crud import get_all_active_clients, create_client

        # Test reading clients
        clients = await get_all_active_clients()
        logger.info(f"✅ Successfully retrieved {len(clients)} clients")

        # If no clients exist, try to create a test one
        if len(clients) == 0:
            logger.info("No clients found, creating test client...")

            test_client = await create_client(
                client_name="Test Client",
                avito_client_id="test_client_123",
                avito_client_secret="test_secret_123"
            )

            if test_client:
                logger.info("✅ Test client created successfully")
            else:
                logger.error("❌ Failed to create test client")

        return True
    except Exception as e:
        logger.error(f"❌ Client CRUD test failed: {e}")
        return False


async def check_encryption_key():
    """Check if encryption key is set"""
    try:
        encryption_key = os.getenv("ENCRYPTION_KEY")
        if encryption_key:
            logger.info("✅ Encryption key found in environment")
            return True
        else:
            logger.error("❌ ENCRYPTION_KEY not found in environment")
            logger.info(
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())\"")
            return False
    except Exception as e:
        logger.error(f"❌ Error checking encryption key: {e}")
        return False


async def main():
    """Run all diagnostic checks"""
    print("🔍 Diagnosing Multi-Client Setup Issues...\n")

    # Check 1: Encryption key
    print("1. Checking encryption key...")
    await check_encryption_key()
    print()

    # Check 2: Database connection
    print("2. Checking database connection...")
    db_ok = await check_database_connection()
    print()

    if not db_ok:
        print("❌ Database connection failed. Check your DATABASE_URL in .env")
        return

    # Check 3: Create tables
    print("3. Creating/updating database tables...")
    await create_tables_if_missing()
    print()

    # Check 4: Check clients table
    print("4. Checking clients table...")
    table_ok = await check_clients_table()
    print()

    if not table_ok:
        print("❌ Clients table still has issues after creation attempt")
        return

    # Check 5: Test CRUD operations
    print("5. Testing client CRUD operations...")
    crud_ok = await test_client_crud()
    print()

    if crud_ok:
        print("✅ All checks passed! Your multi-client setup should work now.")
        print("\nTry accessing: http://your-server:8000/api/clients")
    else:
        print("❌ Some issues remain. Check the logs above.")


if __name__ == "__main__":
    asyncio.run(main())