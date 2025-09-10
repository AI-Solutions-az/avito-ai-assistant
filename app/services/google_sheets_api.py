import httpx, asyncio
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

        return str(size_str).upper()


size_normalizer = SizeNormalizer()


# --- функции парсера ---
async def extract_ad_id_from_url(ad_url: str):
    logger.info(f"[Parser] Извлекаем идентификатор объявления из объявления")
    if not ad_url:
        return None
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
    logger.info(f"[Parser] Получаем список листов с гугл таблицы")
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}?key={API_KEY}"

    max_retries = 2
    for attempt in range(max_retries):
        async with httpx.AsyncClient() as client:
            try:
                if attempt > 0:
                    logger.info(f"[Parser] Повторная попытка {attempt + 1}/{max_retries}")
                    await asyncio.sleep(1)  # Небольшая задержка перед повтором

                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                sheet_names = [s['properties']['title'] for s in data.get('sheets', [])]
                logger.info(f"[Parser] Успешно получен список листов: {sheet_names}")
                return sheet_names

            except Exception as e:
                logger.error(
                    f"[Parser] Ошибка при получении списка листов (попытка {attempt + 1}/{max_retries}): {type(e).__name__}: {str(e)}")
                logger.error(f"[Parser] URL: {url}")

                # Если это HTTP ошибка, логируем статус код и ответ
                if hasattr(e, 'response'):
                    logger.error(f"[Parser] Status code: {e.response.status_code}")
                    logger.error(f"[Parser] Response text: {e.response.text}")

                # Если это последняя попытка, возвращаем пустой список
                if attempt == max_retries - 1:
                    logger.error(f"[Parser] Исчерпаны все попытки получения списка листов")
                    return []


async def search_product_in_sheet(ad_id: str, sheet_name: str):
    """
    Ищем строку с нужным ID на листе. Возвращаем весь массив rows и индекс найденной строки.
    Локальные заголовки будут определяться позже (поднимаясь вверх до ближайшей «шапки»).
    """
    logger.info(f"[Parser] Поиск товара с ID {ad_id} в листе: {sheet_name}")
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{sheet_name}!{RANGE}?majorDimension=ROWS&key={API_KEY}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            if "values" not in data or not data["values"]:
                return None

            rows = data["values"]

            # Находим первую «шапку» листа (не обязательно понадобится)
            headers_row_index = None
            for i, row in enumerate(rows):
                if row and isinstance(row[0], str) and row[0].strip().lower() in ["id", "ид", "артикул", "код"]:
                    headers_row_index = i
                    break

            start_idx = headers_row_index + 1 if headers_row_index is not None else 0
            found_row_index = None

            for i in range(start_idx, len(rows)):
                row = rows[i]
                if not row:
                    continue
                first_cell = row[0] if len(row) > 0 else ""
                ids_in_cell = await parse_ids_from_cell(first_cell)
                if ad_id in ids_in_cell:
                    found_row_index = i
                    break

            if found_row_index is None:
                logger.info(f"[Parser] Товар с ID {ad_id} в листе {sheet_name} НЕ НАЙДЕН")
                return None

            return {
                'sheet_name': sheet_name,
                'found_row_index': found_row_index,
                'rows': rows
            }

        except httpx.HTTPStatusError as e:
            # Специфичная обработка HTTP ошибок
            logger.error(f"[Parser] HTTP ошибка при поиске в листе {sheet_name}: "
                         f"Статус {e.response.status_code}, "
                         f"Ответ: {e.response.text}")
            return None

        except httpx.RequestError as e:
            # Ошибки соединения, таймауты и т.д.
            logger.error(f"[Parser] Ошибка запроса при поиске в листе {sheet_name}: "
                         f"{type(e).__name__}: {str(e)}")
            return None

        except KeyError as e:
            # Ошибки доступа к ключам в JSON
            logger.error(f"[Parser] Ошибка структуры данных в листе {sheet_name}: "
                         f"Отсутствует ключ {e}")
            logger.error(f"[Parser] Полученные данные: {data if 'data' in locals() else 'данные недоступны'}")
            return None

        except Exception as e:
            # Все остальные ошибки с полным стеком вызовов
            logger.error(f"[Parser] Неожиданная ошибка при поиске в листе {sheet_name}: "
                         f"{type(e).__name__}: {str(e)}")
            return None


async def fetch_google_sheet_stock(ad_url: str):
    ad_id = await extract_ad_id_from_url(ad_url)
    if not ad_id:
        return None
    sheet_names = await get_all_sheet_names()
    for sheet_name in sheet_names:
        if sheet_name.lower() == 'knowledge_base':
            continue
        result = await search_product_in_sheet(ad_id, sheet_name)
        if result:
            return await parse_product_from_sheet_data(result, ad_id)
    return None


async def _find_local_header_index(rows, start_from_index: int):
    header_markers = {"id", "ид", "артикул", "код"}
    i = start_from_index
    while i >= 0:
        row = rows[i] if i < len(rows) else []
        first_cell = (row[0].strip().lower() if row and isinstance(row[0], str) else "")
        if first_cell in header_markers:
            return i
        i -= 1
    return None


async def _is_new_header_row(row) -> bool:
    if not row:
        return False
    first_cell = (row[0].strip().lower() if isinstance(row[0], str) else "")
    return first_cell in {"id", "ид", "артикул", "код"}


async def parse_product_from_sheet_data(sheet_data, ad_id: str):
    """
    Для найденной строки:
      1) поднимаемся вверх до ближайшей строки-шапки (id/ид/артикул/код),
      2) используем её как локальные заголовки,
      3) собираем строки блока до следующей шапки/пустой строки/строки другого товара,
      4) парсим с локальными заголовками.
    """
    logger.info("[Parser] Парсим найденный товар с листа")
    try:
        sheet_name = sheet_data['sheet_name']
        rows = sheet_data['rows']
        found_row_index = sheet_data['found_row_index']

        # 1) Локальная шапка
        header_row_index = await _find_local_header_index(rows, found_row_index - 1)
        if header_row_index is None:
            return None

        local_headers = rows[header_row_index]

        # 2) Собираем блок строк
        product_rows = []
        logger.info("[Parser] Парсим идентификаторы объявлений из ячейки")
        found_ids = await parse_ids_from_cell(rows[found_row_index][0]) if rows[found_row_index] else []
        current_index = found_row_index

        while current_index < len(rows):
            row = rows[current_index]
            if not row:
                break

            if await _is_new_header_row(row) and current_index != found_row_index:
                break

            if current_index > found_row_index and len(row) > 0 and row[0]:
                logger.info("[Parser] Парсим идентификаторы объявлений из ячейки")
                current_ids = await parse_ids_from_cell(row[0])
                if current_ids and not any(_id in found_ids for _id in current_ids):
                    break

            if len(row) > 3:
                product_rows.append(row)

            current_index += 1

        if not product_rows:
            return None

        return await parse_stock_with_all_info(local_headers, product_rows, ad_id, sheet_name)

    except Exception as e:
        logger.error(f"[Parser] Ошибка при парсинге данных из листа: {e}")
        return None


async def parse_stock_with_all_info(headers, product_rows, ad_id: str, category: str):
    try:
        async def safe_get(lst, index, default=''):
            try:
                value = lst[index] if index < len(lst) else default
                if value is None:
                    return default
                return value.strip() if isinstance(value, str) else value
            except (IndexError, TypeError):
                return default

        header_lower = [(h.lower().strip() if isinstance(h, str) else "") for h in headers]

        name_col = 1 if len(headers) > 1 else None
        price_col = 2 if len(headers) > 2 else None

        color_col = None
        for i, h in enumerate(header_lower):
            if h and ("цвет" in h or "color" in h):
                color_col = i
                break
        if color_col is None:
            color_col = 3 if len(headers) > 3 else None

        description_col = None
        size_info_col = None
        for i, h in enumerate(header_lower):
            if not h:
                continue
            if description_col is None and ("описание" in h or "description" in h):
                description_col = i
            elif size_info_col is None and ("размер" in h and "описан" not in h):
                size_info_col = i

        base_idx = (color_col + 1) if color_col is not None else ((price_col + 1) if price_col is not None else 4)

        size_columns = {}
        for i in range(base_idx, len(headers)):
            header_text = headers[i].strip() if i < len(headers) and isinstance(headers[i], str) else ""
            if not header_text:
                continue
            normalized = await size_normalizer.normalize(header_text)
            if normalized in ['XS', 'S', 'M', 'L', 'XL', 'XXL', 'XXXL', 'XXXXL', 'XXXXXL'] or re.search(r'\d+', normalized):
                size_columns[i] = normalized

        # Photo column
        photo_col = None
        photo_pattern = re.compile(r'(фото|photo|image|pic)', re.IGNORECASE)
        photo_id_pattern = re.compile(r'(?:фото|photo|image|pic)[ _-]*id|id[ _-]*(?:фото|photo|image|pic)', re.IGNORECASE)
        for i in range(base_idx, len(headers)):
            h = header_lower[i]
            if not h or h == "id":
                continue
            if photo_pattern.search(h) or photo_id_pattern.search(h):
                photo_col = i
                break
        if photo_col is None and size_columns:
            last_size_idx = max(size_columns.keys())
            candidate = last_size_idx + 1
            if candidate < len(headers):
                cand_header = header_lower[candidate]
                if "описание" in cand_header or "description" in cand_header:
                    if candidate + 1 < len(headers):
                        candidate += 1
                photo_col = candidate

        first_row = product_rows[0]
        product = {
            'id': ad_id,   # 👈 теперь только цифры!
            'category': category,
            'name': await safe_get(first_row, name_col) if name_col is not None else '',
            'price': await safe_get(first_row, price_col, '') if price_col is not None else '',
            'description': await safe_get(first_row, description_col) if description_col is not None else '',
            'size_info': await safe_get(first_row, size_info_col) if size_info_col is not None else '',
            'payment_method': '',
            'delivery_method': '',
            'photo_ids': '',
            'stock': []
        }

        if photo_col is not None:
            photos = []
            for row in product_rows:
                val = await safe_get(row, photo_col, '')
                if val:
                    photos.append(str(val).strip())
            if photos:
                uniq = []
                seen = set()
                for p in photos:
                    if p not in seen:
                        seen.add(p)
                        uniq.append(p)
                product['photo_ids'] = ", ".join(uniq)

        for row in product_rows:
            color_val = await safe_get(row, color_col) if color_col is not None else ''
            if not color_val:
                continue
            stock_item = {'color': color_val, 'sizes': {}}
            for col_index, size_name in size_columns.items():
                quantity_raw = await safe_get(row, col_index, '0')
                try:
                    quantity = int(quantity_raw) if str(quantity_raw).isdigit() else 0
                except ValueError:
                    quantity = 0
                stock_item['sizes'][size_name] = "Есть в наличии" if quantity > 0 else "Нет в наличии"
            stock_item['has_available_sizes'] = any(v == "Есть в наличии" for v in stock_item['sizes'].values())
            product['stock'].append(stock_item)

        product['has_stock'] = any(item['has_available_sizes'] for item in product['stock'])
        product['available_colors'] = [item['color'] for item in product['stock'] if item['has_available_sizes']]

        json_result = json.dumps(product, ensure_ascii=False, indent=4)
        print("=== JSON результат парсера ===")
        print(json_result)
        print("=== Конец JSON ===")

        return json_result

    except Exception as e:
        logger.error(f'[Parser] Ошибка при парсинге строки из документа: {e}')
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
            except Exception as e:
                logger.error(f"[Parser] Ошибка при чтении листа {sheet_name}: {e}")
                continue
    return None
