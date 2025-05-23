# app/services/avito_api.py - REPLACE your existing file with this version

import httpx
import asyncio
from time import time
from app.services.logs import logger
from db.client_crud import get_client_by_avito_id

# Token cache for multiple clients
_client_tokens = {}
_client_token_expiry = {}
_locks = {}


async def get_avito_token(client_id: str) -> str:
    """Get token for specific client with caching"""

    # Create lock for this client if it doesn't exist
    if client_id not in _locks:
        _locks[client_id] = asyncio.Lock()

    async with _locks[client_id]:
        # Check if we have a valid cached token
        if (client_id in _client_tokens and
                client_id in _client_token_expiry and
                time() < _client_token_expiry[client_id]):
            return _client_tokens[client_id]

        # Get client credentials from database
        client = await get_client_by_avito_id(client_id)
        if not client:
            logger.error(f"Client {client_id} not found in database")
            raise ValueError(f"Client {client_id} not found")

        logger.info(f"Requesting new token for client {client_id}")
        url = "https://api.avito.ru/token/"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": client.avito_client_id,
            "client_secret": client.avito_client_secret
        }

        try:
            async with httpx.AsyncClient() as http_client:
                response = await http_client.post(url, headers=headers, data=data)
                response.raise_for_status()
                token_data = response.json()

                # Cache the token
                _client_tokens[client_id] = token_data.get("access_token", "")
                _client_token_expiry[client_id] = time() + token_data.get("expires_in", 3600) - 60

                logger.info(f"Token obtained successfully for client {client_id}")
                return _client_tokens[client_id]

        except httpx.RequestError as e:
            logger.error(f"Error getting token for client {client_id}: {e}")
            raise


async def send_message(user_id: int, chat_id: str, text: str, client_avito_id: str) -> None:
    """Send message with client-specific authentication"""
    logger.info(f"Sending message to user {user_id} in chat {chat_id} for client {client_avito_id}")

    url = f"https://api.avito.ru/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages"
    headers = {
        "Authorization": f"Bearer {await get_avito_token(client_avito_id)}",
        "Content-Type": "application/json"
    }
    payload = {"message": {"text": text}, "type": "text"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"Message sent successfully for client {client_avito_id}")
    except httpx.RequestError as e:
        logger.error(f"Error sending message for client {client_avito_id}: {e}")
        raise


async def get_ad(user_id: int, item_id: int, client_avito_id: str) -> str:
    """Get ad information with client-specific authentication"""
    logger.info(f"Getting ad info for client {client_avito_id}, user {user_id}, item {item_id}")

    url = f"https://api.avito.ru/core/v1/accounts/{user_id}/items/{item_id}/"
    headers = {
        "Authorization": f"Bearer {await get_avito_token(client_avito_id)}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            ad_url = response.json().get("url", "")
            logger.info(f"Ad info obtained for client {client_avito_id}: {ad_url}")
            return ad_url
    except httpx.RequestError as e:
        logger.error(f"Error getting ad info for client {client_avito_id}: {e}")
        raise


async def get_user_info(user_id, chat_id, client_avito_id: str):
    """Get user info with client-specific authentication"""
    logger.info(f"Getting user info for client {client_avito_id}, user {user_id}, chat {chat_id}")

    url = f"https://api.avito.ru/messenger/v2/accounts/{user_id}/chats/{chat_id}"
    headers = {
        "Authorization": f"Bearer {await get_avito_token(client_avito_id)}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            user_info = response.json()
            logger.info(f"User info obtained for client {client_avito_id}")

            # Extract user name and URL (excluding the business account)
            user_name = next((user['name'] for user in user_info['users'] if user['name'] != 'TryFashion'), None)
            user_url = next(
                (user['public_user_profile']['url'] for user in user_info['users'] if user['name'] != 'TryFashion'),
                None)

            return user_name, user_url

    except httpx.RequestError as e:
        logger.error(f"Error getting user info for client {client_avito_id}: {e}")
        return None, None