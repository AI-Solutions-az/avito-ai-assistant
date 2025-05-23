# app/routes/client_management.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from db.client_crud import (
    create_client, get_client_by_avito_id, get_all_active_clients,
    update_client, deactivate_client
)
from app.services.logs import logger

router = APIRouter()


class ClientCreateRequest(BaseModel):
    client_name: str
    avito_client_id: str
    avito_client_secret: str
    openai_api_key: Optional[str] = None
    openai_assistant_id: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_thread_id: Optional[int] = None
    google_api_key: Optional[str] = None
    google_spreadsheet_id: Optional[str] = None
    google_range: Optional[str] = None
    warehouse_sheet_name: Optional[str] = None
    knowledge_base_sheet_name: Optional[str] = None


class ClientUpdateRequest(BaseModel):
    client_name: Optional[str] = None
    avito_client_secret: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_assistant_id: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_thread_id: Optional[int] = None
    google_api_key: Optional[str] = None
    google_spreadsheet_id: Optional[str] = None
    google_range: Optional[str] = None
    warehouse_sheet_name: Optional[str] = None
    knowledge_base_sheet_name: Optional[str] = None
    is_active: Optional[bool] = None


class ClientResponse(BaseModel):
    id: int
    client_name: str
    avito_client_id: str
    openai_assistant_id: Optional[str]
    telegram_chat_id: Optional[str]
    telegram_thread_id: Optional[int]
    google_spreadsheet_id: Optional[str]
    google_range: Optional[str]
    warehouse_sheet_name: Optional[str]
    knowledge_base_sheet_name: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str


@router.post("/clients", response_model=dict)
async def create_new_client(client_data: ClientCreateRequest):
    """Create a new client"""
    try:
        # Check if client already exists
        existing_client = await get_client_by_avito_id(client_data.avito_client_id)
        if existing_client:
            raise HTTPException(status_code=400, detail="Client with this Avito ID already exists")

        client = await create_client(
            client_name=client_data.client_name,
            avito_client_id=client_data.avito_client_id,
            avito_client_secret=client_data.avito_client_secret,
            openai_api_key=client_data.openai_api_key,
            openai_assistant_id=client_data.openai_assistant_id,
            telegram_bot_token=client_data.telegram_bot_token,
            telegram_chat_id=client_data.telegram_chat_id,
            telegram_thread_id=client_data.telegram_thread_id,
            google_api_key=client_data.google_api_key,
            google_spreadsheet_id=client_data.google_spreadsheet_id,
            google_range=client_data.google_range,
            warehouse_sheet_name=client_data.warehouse_sheet_name,
            knowledge_base_sheet_name=client_data.knowledge_base_sheet_name
        )

        if not client:
            raise HTTPException(status_code=500, detail="Failed to create client")

        return {"message": "Client created successfully", "client_id": client.id}

    except Exception as e:
        logger.error(f"Error creating client: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clients", response_model=List[ClientResponse])
async def list_clients():
    """Get all active clients"""
    try:
        clients = await get_all_active_clients()
        return [
            ClientResponse(
                id=client.id,
                client_name=client.client_name,
                avito_client_id=client.avito_client_id,
                openai_assistant_id=client.openai_assistant_id,
                telegram_chat_id=client.telegram_chat_id,
                telegram_thread_id=client.telegram_thread_id,
                google_spreadsheet_id=client.google_spreadsheet_id,
                google_range=client.google_range,
                warehouse_sheet_name=client.warehouse_sheet_name,
                knowledge_base_sheet_name=client.knowledge_base_sheet_name,
                is_active=client.is_active,
                created_at=client.created_at.isoformat() if client.created_at else "",
                updated_at=client.updated_at.isoformat() if client.updated_at else ""
            )
            for client in clients
        ]
    except Exception as e:
        logger.error(f"Error listing clients: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clients/{avito_client_id}", response_model=ClientResponse)
async def get_client(avito_client_id: str):
    """Get specific client by Avito ID"""
    try:
        client = await get_client_by_avito_id(avito_client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        return ClientResponse(
            id=client.id,
            client_name=client.client_name,
            avito_client_id=client.avito_client_id,
            openai_assistant_id=client.openai_assistant_id,
            telegram_chat_id=client.telegram_chat_id,
            telegram_thread_id=client.telegram_thread_id,
            google_spreadsheet_id=client.google_spreadsheet_id,
            google_range=client.google_range,
            warehouse_sheet_name=client.warehouse_sheet_name,
            knowledge_base_sheet_name=client.knowledge_base_sheet_name,
            is_active=client.is_active,
            created_at=client.created_at.isoformat() if client.created_at else "",
            updated_at=client.updated_at.isoformat() if client.updated_at else ""
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting client: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/clients/{client_id}")
async def update_client_info(client_id: int, update_data: ClientUpdateRequest):
    """Update client information"""
    try:
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}

        client = await update_client(client_id, **update_dict)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        return {"message": "Client updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating client: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clients/{client_id}")
async def delete_client(client_id: int):
    """Deactivate a client (soft delete)"""
    try:
        client = await deactivate_client(client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        return {"message": "Client deactivated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating client: {e}")
        raise HTTPException(status_code=500, detail=str(e))