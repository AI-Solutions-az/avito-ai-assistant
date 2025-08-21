import httpx
import json
import re
from app.services.logs import logger
from app.config import RANGE, SPREADSHEET_ID, API_KEY


# 🔥 Нормализатор размеров
class SizeNormalizer:
    def __init__(self):
        self.numeric_to_letter = {
            "42": "XS", "44": "S", "46": "S", "48": "M",
            "50": "L", "52": "XL", "54": "XXL", "56": "XXXL",
            "58": "XXXXL", "60": "XXXXXL"
        }
        self.letter_variants = {
            "XS": ["xs", "xс", "хс"],
            "S": ["s", "c", "с"],
            "M": ["m", "м"],
            "L": ["l", "л"],
            "XL": ["xl", "хл", "xл"],
            "XXL": ["xxl", "2xl", "2хл", "ххл"],
            "XXXL": ["xxxl", "3xl", "3хл", "хххл"],
            "XXXXL": ["xxxxl", "4xl", "4хл", "ххххл"],
            "XXXXXL": ["xxxxxl", "5xl", "5хл", "хххххл"]
        }

    async def normalize(self, size_str: str) -> str:
        if not size_str:
            return ""
        s = str(size_str).strip().lower()

        # заменяем кириллицу на латиницу
        replacements = {"с": "s", "х": "x", "л": "l", "м": "m"}
        for old, new in replacements.items():
            s = s.replace(old, new)

        # буквенные размеры
        for letter, variants in self.letter_variants.items():
            if s in variants or s == letter.lower():
                return letter

        # числовые размеры
        numbers = re.findall(r"\d+", s)
        if numbers:
            num = numbers[0]
            if num in self.numeric_to_letter:
                return self.numeric_to_letter[num]

        # EU/IT форматы
        if s.startswith(("eu", "it")):
            digits = re.sub(r"\D", "", s)
            if digits in self.numeric_to_letter:
                return self.numeric_to_letter[digits]

        return size_str.upper()


size_normalizer = SizeNormalizer()


# --- функции парсера ---
async def extract_ad_id_from_url(ad_url):
    match = re.search(r'_(\d+)$', ad_url)
    if match:
        return match.group(1)
    match = re.search(r'/(\d{7,})(?:/|$)', ad_url)
    if match:
        return match.group(1)
    return None


async def parse_ids_from_cell(cell_value):
    if not cell_value:
        return []
    cell_value = str(cell_value).strip()
    ids = re.split(r'[,\s]+', cell_value)
    return [id_str.strip() for id_str in ids if id_str.strip().isdigit()]


async def get_all_sheet_names():
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}?key={API_KEY}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            return [s['properties']['title'] for s in data.get('sheets', [])]
        except Exception as e:
            logger.error(f"Ошибка при получении списка листов: {e}")
            return []


async def search_product_in_sheet(ad_id, sheet_name):
    logger.info(f"Поиск товара с ID {ad_id} в листе: {sheet_name}")
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{sheet_name}!{RANGE}?majorDimension=ROWS&key={API_KEY}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            if "values" not in data or not data["values"]:
                return None

            rows = data["values"]
            headers_row_index = None
            for i, row in enumerate(rows):
                if row and row[0].lower() in ["id", "ид", "артикул", "код"]:
                    headers_row_index = i
                    break
            if headers_row_index is None:
                return None

            headers = rows[headers_row_index]
            id_column_index = 0
            found_row_index = None

            for i in range(headers_row_index + 1, len(rows)):
                row = rows[i]
                if len(row) > id_column_index and row[id_column_index]:
                    ids_in_cell = await parse_ids_from_cell(row[id_column_index])
                    if ad_id in ids_in_cell:
                        found_row_index = i
                        break

            if found_row_index is None:
                return None

            return {
                'sheet_name': sheet_name,
                'headers': headers,
                'found_row_index': found_row_index,
                'rows': rows
            }
        except Exception as e:
            logger.error(f"Ошибка при поиске в листе {sheet_name}: {e}")
            return None


async def fetch_google_sheet_stock(ad_url):
    ad_id = await extract_ad_id_from_url(ad_url)
    if not ad_id:
        return None
    sheet_names = await get_all_sheet_names()
    for sheet_name in sheet_names:
        if sheet_name.lower() == 'knowledge_base':
            continue
        result = await search_product_in_sheet(ad_id, sheet_name)
        if result:
            return await parse_product_from_sheet_data(result, ad_url)
    return None


async def parse_product_from_sheet_data(sheet_data, ad_url):
    try:
        sheet_name = sheet_data['sheet_name']
        headers = sheet_data['headers']
        rows = sheet_data['rows']
        found_row_index = sheet_data['found_row_index']

        product_rows = []
        current_index = found_row_index
        found_ids = await parse_ids_from_cell(rows[found_row_index][0])

        while current_index < len(rows):
            row = rows[current_index]
            if not row or (row and row[0].lower() in ["id", "ид", "артикул", "код"]):
                break
            if current_index > found_row_index and len(row) > 0 and row[0]:
                current_ids = await parse_ids_from_cell(row[0])
                if not any(id in found_ids for id in current_ids):
                    break
            if len(row) > 3 and row[3]:
                product_rows.append(row)
            current_index += 1

        if not product_rows:
            return None

        return await parse_stock_with_availability_only(headers, product_rows, ad_url, sheet_name)
    except Exception as e:
        logger.error(f"Ошибка при парсинге данных из листа: {e}")
        return None


async def parse_stock_with_availability_only(headers, product_rows, ad_url, category):
    try:
        async def safe_get(lst, index, default=''):
            try:
                value = lst[index] if index < len(lst) else default
                return value.strip() if isinstance(value, str) else value
            except (IndexError, TypeError):
                return default

        first_row = product_rows[0]
        product = {
            'id': ad_url,
            'category': category,
            'name': await safe_get(first_row, 1),
            'price': '',
            'description': '',
            'size_info': '',
            'payment_method': '',
            'delivery_method': '',
            'photo_ids': '',
            'stock': []
        }

        for row in product_rows:
            color = await safe_get(row, 3)
            if not color:
                continue
            stock_item = {'color': color, 'sizes': {}}

            size_mapping = {}
            for i in range(4, len(headers)):
                header = headers[i].strip() if i < len(headers) and headers[i] else ''
                if not header:
                    break
                normalized = await size_normalizer.normalize(header)
                size_mapping[i] = normalized

            for col_index, size_name in size_mapping.items():
                quantity = await safe_get(row, col_index, '0')
                try:
                    quantity = int(quantity) if quantity else 0
                except ValueError:
                    quantity = 0
                stock_item['sizes'][size_name] = "Есть в наличии" if quantity > 0 else "Нет в наличии"

            stock_item['has_available_sizes'] = any(v == "Есть в наличии" for v in stock_item['sizes'].values())
            product['stock'].append(stock_item)

        product['has_stock'] = any(item['has_available_sizes'] for item in product['stock'])
        product['available_colors'] = [item['color'] for item in product['stock'] if item['has_available_sizes']]

        # 🔥 Вывод JSON прямо здесь
        json_result = json.dumps(product, ensure_ascii=False, indent=4)
        print("=== JSON результат парсера ===")
        print(json_result)
        print("=== Конец JSON ===")

        return json_result

    except Exception as e:
        logger.error(f'Ошибка при парсинге строки из документа: {e}')
        return None


async def get_knowledge_base():
    knowledge_sheet_names = ['knowledge_base']
    for sheet_name in knowledge_sheet_names:
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{sheet_name}!{RANGE}?majorDimension=ROWS&key={API_KEY}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                if "values" not in data or not data["values"]:
                    continue
                result = []
                for row in data["values"]:
                    if len(row) >= 2:
                        result.append({'question': row[0], 'answer_example': row[1]})
                    elif len(row) == 1:
                        result.append({'question': row[0], 'answer_example': ''})
                return json.dumps(result, ensure_ascii=False, indent=2)
            except Exception:
                continue
    return None
