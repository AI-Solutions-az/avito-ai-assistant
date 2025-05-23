# app/services/client_google_sheets_api.py

import httpx
import json
from app.services.logs import logger
from db.client_crud import get_client_by_avito_id


async def fetch_google_sheet_stock(ad_url, client_avito_id):
    '''
    Client-specific Google Sheets stock fetching
    :param ad_url: Advertisement URL to search for
    :param client_avito_id: Client's Avito ID to get their specific configuration
    :return: JSON data with product availability
    '''
    # Get client configuration
    client = await get_client_by_avito_id(client_avito_id)
    if not client:
        logger.error(f"Client {client_avito_id} not found")
        return None

    if not client.google_api_key or not client.google_spreadsheet_id:
        logger.error(f"Google Sheets configuration missing for client {client_avito_id}")
        return None

    # Use client-specific configuration
    api_key = client.google_api_key
    spreadsheet_id = client.google_spreadsheet_id
    sheet_name = client.warehouse_sheet_name or "Sheet1"
    range_val = client.google_range or "A:Z"

    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{sheet_name}!{range_val}?majorDimension=ROWS&key={api_key}"

    async with httpx.AsyncClient() as http_client:
        try:
            response = await http_client.get(url)
            response.raise_for_status()
            data = response.json()

            if "values" not in data or not data["values"]:
                logger.error(f"No data found in Google Sheets for client {client_avito_id}")
                return None

            headers = data["values"][0]
            rows = data["values"][0:]

            ad_column_index = 1  # Column B (0-indexed)
            found_row_num = None

            for row_num, row in enumerate(rows, start=0):
                if len(row) > ad_column_index and row[ad_column_index] == ad_url:
                    logger.info(f"Advertisement found in row {row_num} for client {client_avito_id}")
                    found_row_num = row_num
                    break

            if found_row_num is None:
                logger.error(f"Advertisement not found in sheet for client {client_avito_id}")
                return None

            extracted_rows = []
            for row in rows[found_row_num:]:
                if not row:
                    break
                extracted_rows.append(row)

            if not extracted_rows:
                logger.error(f"No product data found for client {client_avito_id}")
                return None

            return await parse_stock(extracted_rows)

        except httpx.RequestError as e:
            logger.error(f"Error fetching Google Sheets data for client {client_avito_id}: {e}")
            return None


async def parse_stock(data):
    '''
    Parse product information from Google Sheets data
    :param data: Raw sheet data
    :return: Formatted JSON product data
    '''
    try:
        headers = data[0]
        product_info = data[1]

        def safe_get(lst, index, default=''):
            try:
                return lst[index] if index < len(lst) else default
            except (IndexError, TypeError):
                return default

        product = {
            'id': safe_get(product_info, 1),
            'name': safe_get(product_info, 2),
            'price': safe_get(product_info, 11),
            'description': safe_get(product_info, 12),
            'size_info': safe_get(product_info, 13),
            'payment_method': safe_get(product_info, 14),
            'delivery_method': safe_get(product_info, 15),
            'current_stock': []
        }

        # Parse color and size matrix (columns 5-11)
        for row in data[1:]:
            color = safe_get(row, 4)
            sizes = []

            for i in range(5, 11):
                sizes.append(safe_get(row, i, ''))

            while len(sizes) < 6:
                sizes.append('')

            product['current_stock'].append({
                'color': color,
                'sizes': {safe_get(headers, i, f'Size{i - 4}'): sizes[i - 5] for i in range(5, 11)}
            })

        return json.dumps(product, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f'Error parsing Google Sheets data: {e}')
        return None


async def get_knowledge_base(client_avito_id):
    '''
    Get client-specific knowledge base from Google Sheets
    :param client_avito_id: Client's Avito ID
    :return: JSON formatted knowledge base
    '''
    client = await get_client_by_avito_id(client_avito_id)
    if not client:
        logger.error(f"Client {client_avito_id} not found")
        return None

    if not client.google_api_key or not client.google_spreadsheet_id:
        logger.error(f"Google Sheets configuration missing for client {client_avito_id}")
        return None

    api_key = client.google_api_key
    spreadsheet_id = client.google_spreadsheet_id
    sheet_name = client.knowledge_base_sheet_name or "KnowledgeBase"
    range_val = client.google_range or "A:Z"

    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{sheet_name}!{range_val}?majorDimension=ROWS&key={api_key}"

    async with httpx.AsyncClient() as http_client:
        try:
            response = await http_client.get(url)
            response.raise_for_status()
            data = response.json()

            if "values" not in data or not data["values"]:
                logger.error(f"No knowledge base data found for client {client_avito_id}")
                return None

            result = []
            for row in data["values"]:
                if len(row) >= 2:
                    question_answer = {
                        'question': row[0],
                        'answer_example': row[1]
                    }
                    result.append(question_answer)
                elif len(row) == 1:
                    question_answer = {
                        'question': row[0],
                        'answer_example': ''
                    }
                    result.append(question_answer)

            return json.dumps(result, ensure_ascii=False, indent=2)

        except httpx.RequestError as e:
            logger.error(f"Error fetching knowledge base for client {client_avito_id}: {e}")
            return None