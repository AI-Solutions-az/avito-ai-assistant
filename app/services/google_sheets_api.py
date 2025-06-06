import httpx
import json
import re
from app.services.logs import logger
from app.config import RANGE, SPREADSHEET_ID, WAREHOUSE_SHEET_NAME, KNOWLEDGE_BASE_SHEET_NAME, API_KEY


def extract_ad_id_from_url(ad_url):
    """
    Извлекает ID объявления из URL.
    Примеры:
    - https://www.avito.ru/moskva/odezhda_obuv_aksessuary/hudi_stussy_2xl_7352154008 -> 7352154008
    - https://www.avito.ru/moskva/odezhda_obuv_aksessuary/svitshot_lyle_scott_7352966820 -> 7352966820
    """
    match = re.search(r'_(\d+)$', ad_url)
    if match:
        return match.group(1)
    # Если не найдено в конце, попробуем найти последовательность цифр
    match = re.search(r'/(\d{7,})(?:/|$)', ad_url)
    if match:
        return match.group(1)
    return None


def parse_ids_from_cell(cell_value):
    """
    Извлекает все ID из ячейки, где ID могут быть разделены запятыми или пробелами.
    Возвращает список ID.
    """
    if not cell_value:
        return []

    # Преобразуем в строку на случай если это число
    cell_value = str(cell_value).strip()

    # Заменяем запятые на пробелы и разбиваем по пробелам
    ids = re.split(r'[,\s]+', cell_value)

    # Фильтруем только валидные ID (цифры)
    valid_ids = [id_str.strip() for id_str in ids if id_str.strip().isdigit()]

    return valid_ids


async def fetch_google_sheet_stock(ad_url):
    '''
    Поиск строки с идентификатором объявления
    Парсинг строки
    Возврат json'а с данными по товару и его доступности
    :param ad_url:
    :return:
    '''
    # Извлекаем ID из URL
    ad_id = extract_ad_id_from_url(ad_url)
    if not ad_id:
        logger.error(f"Не удалось извлечь ID из URL: {ad_url}")
        return None

    logger.info(f"Ищем объявление с ID: {ad_id}")

    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{WAREHOUSE_SHEET_NAME}!{RANGE}?majorDimension=ROWS&key={API_KEY}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            if "values" not in data or not data["values"]:
                logger.error("Ошибка: данные не найдены")
                return None

            rows = data["values"]

            # Ищем заголовки (строка с "Id" в первой колонке)
            headers_row_index = None
            for i, row in enumerate(rows):
                if row and row[0] == "Id":
                    headers_row_index = i
                    break

            if headers_row_index is None:
                logger.error("Ошибка: заголовки не найдены")
                return None

            headers = rows[headers_row_index]
            logger.info(f"Найденные заголовки: {headers}")

            # Ищем строку с нужным ID
            id_column_index = 0  # Колонка A
            found_row_index = None

            for i in range(headers_row_index + 1, len(rows)):
                row = rows[i]
                if len(row) > id_column_index and row[id_column_index]:
                    # Извлекаем все ID из ячейки
                    ids_in_cell = parse_ids_from_cell(row[id_column_index])
                    # Проверяем, есть ли наш ID среди них
                    if ad_id in ids_in_cell:
                        logger.info(f"Объявление с ID {ad_id} найдено в строке {i + 1}")
                        found_row_index = i
                        break

            if found_row_index is None:
                logger.error(f"Ошибка: объявление с ID {ad_id} не найдено")
                return None

            # Для каждого товара нужно определить его размерную сетку
            # Находим строку заголовков для текущего товара
            product_headers_index = None
            for i in range(found_row_index - 1, max(0, found_row_index - 5), -1):
                if rows[i] and rows[i][0] == "Id":
                    product_headers_index = i
                    break

            if product_headers_index is None:
                # Если не нашли заголовки выше, используем основные
                product_headers_index = headers_row_index

            product_headers = rows[product_headers_index]
            logger.info(f"Заголовки для товара: {product_headers}")

            # Извлекаем все строки для данного товара
            product_rows = []
            current_index = found_row_index

            # Получаем все ID из найденной строки
            found_ids = parse_ids_from_cell(rows[found_row_index][id_column_index])
            logger.info(f"ID в найденной строке: {found_ids}")

            while current_index < len(rows):
                row = rows[current_index]
                logger.info(f"Обрабатываем строку {current_index + 1}: {row[:5] if len(row) > 5 else row}")

                # Если строка пустая или начинается новый блок заголовков
                if not row or (row and row[0] == "Id"):
                    logger.info("Встретили пустую строку или новый блок заголовков")
                    break

                # Если встретили новый набор ID в колонке A (новый товар)
                if current_index > found_row_index and len(row) > id_column_index and row[id_column_index]:
                    current_ids = parse_ids_from_cell(row[id_column_index])
                    # Проверяем, что это не те же ID
                    if not any(id in found_ids for id in current_ids):
                        logger.info(f"Встретили новый товар с ID: {current_ids}")
                        break

                # Добавляем строку только если есть данные о цвете
                # Цвет находится в колонке D (индекс 3) из-за пустой колонки
                if len(row) > 3 and row[3]:  # Проверяем наличие цвета в колонке D
                    product_rows.append(row)
                    logger.info(f"Добавлена строка с цветом: {row[3]}")
                else:
                    logger.info(f"Пропущена строка без цвета")

                current_index += 1

            if not product_rows:
                logger.error("Ошибка: данные о товаре не найдены")
                return None

            return parse_stock(product_headers, product_rows, ad_url)

        except httpx.RequestError as e:
            logger.error(f"Ошибка при запросе: {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP ошибка: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")
            return None


def parse_stock(headers, product_rows, ad_url):
    '''
    Парсинг информации о найденной по идентификатору строке
    :param headers: Заголовки колонок
    :param product_rows: Строки с данными о товаре
    :param ad_url: URL объявления
    :return:
    '''
    try:
        if not product_rows:
            logger.error("Нет данных для парсинга")
            return None

        # Функция для безопасного получения значения из списка
        def safe_get(lst, index, default=''):
            try:
                value = lst[index] if index < len(lst) else default
                return value.strip() if isinstance(value, str) else value
            except (IndexError, TypeError):
                return default

        # Берем первую строку товара для основной информации
        first_row = product_rows[0]

        # Находим индексы колонок для описания, размеров и фото
        description_index = None
        size_info_index = None
        photo_ids_index = None

        for i, header in enumerate(headers):
            if "Описание" in header:
                description_index = i
            elif "Размеры" in header and "размер" in header.lower():
                size_info_index = i
            elif "фото" in header.lower() and "id" in header.lower():
                photo_ids_index = i

        product = {
            'id': ad_url,
            'name': safe_get(first_row, 1),  # Товар в колонке B
            'price': '',  # Цена не указана в новой структуре
            'description': safe_get(first_row, description_index) if description_index else '',
            'size_info': safe_get(first_row, size_info_index) if size_info_index else '',
            'payment_method': '',  # Не указано в новой структуре
            'delivery_method': '',  # Не указано в новой структуре
            'photo_ids': safe_get(first_row, photo_ids_index) if photo_ids_index else '',
            'stock': []
        }

        # Обрабатываем каждую строку с цветом
        for row in product_rows:
            color = safe_get(row, 3)  # Цвет в колонке D (индекс 3)
            if not color:
                continue

            # Собираем информацию о размерах (колонки E-L, индексы 4-11)
            stock_item = {
                'color': color,
                'sizes': {}
            }

            # Размеры: динамически определяем из заголовков
            # Находим начало и конец колонок с размерами
            size_mapping = {}
            size_start_index = 4  # Начинаем с колонки E (после Id, Товар, пустая, Цвет)

            # Ищем где заканчиваются размеры (до колонок с описанием)
            for i in range(size_start_index, len(headers)):
                header = headers[i].strip() if i < len(headers) and headers[i] else ''

                # Проверяем, что это размер, а не описание
                if header and not any(word in header.lower() for word in ['описание', 'размер', 'фото', '(i)']):
                    # Это размер
                    size_name = header
                    # Нормализуем названия размеров для единообразия
                    if size_name == '2XL':
                        size_name = 'XXL (2XL)'
                    elif size_name == '3XL' or size_name == '3Xl':
                        size_name = 'XXXL (3XL)'
                    elif size_name == '4XL':
                        size_name = 'XXXXL (4XL)'
                    elif size_name == 'XXL':
                        size_name = 'XXL (2XL)'
                    elif size_name == 'XXXL':
                        size_name = 'XXXL (3XL)'
                    elif size_name == 'XS':
                        size_name = 'XS'
                    elif size_name == 'S':
                        size_name = 'S'
                    elif size_name == 'M' or size_name == 'М':  # Иногда может быть кириллица
                        size_name = 'M'
                    elif size_name == 'L':
                        size_name = 'L'
                    elif size_name == 'XL':
                        size_name = 'XL'

                    size_mapping[i] = size_name
                    logger.info(f"Найден размер '{header}' -> '{size_name}' в колонке {i}")
                elif header:
                    # Встретили не-размерную колонку, прекращаем поиск размеров
                    break

            if not size_mapping:
                logger.warning("Не найдены колонки с размерами, используем стандартный диапазон")
                # Если размеры не найдены, пробуем стандартный диапазон
                for i in range(4, min(12, len(headers))):
                    if i < len(headers) and headers[i] and headers[i].strip():
                        size_mapping[i] = headers[i].strip()

            logger.info(f"Итоговая карта размеров: {size_mapping}")

            for col_index, size_name in size_mapping.items():
                quantity = safe_get(row, col_index, '0')
                # Преобразуем в число, если это возможно
                try:
                    quantity = int(quantity) if quantity else 0
                except ValueError:
                    quantity = 0
                stock_item['sizes'][size_name] = quantity

            # Подсчитываем общее количество для данного цвета
            stock_item['total_quantity'] = sum(stock_item['sizes'].values())

            # Добавляем только если есть хотя бы один товар в наличии
            if stock_item['total_quantity'] > 0 or all(qty == 0 for qty in stock_item['sizes'].values()):
                product['stock'].append(stock_item)

        # Добавляем сводную информацию
        product['total_stock'] = sum(item['total_quantity'] for item in product['stock'])
        product['available_colors'] = [item['color'] for item in product['stock'] if item['total_quantity'] > 0]

        return json.dumps(product, ensure_ascii=False, indent=4)

    except Exception as e:
        logger.error(f'Ошибка при парсинге строки из документа: {e}')
        return None


async def get_knowledge_base():
    '''
    Получение информации из базы знаний
    :return:
    '''
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{KNOWLEDGE_BASE_SHEET_NAME}!{RANGE}?majorDimension=ROWS&key={API_KEY}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()  # Проверка успешности запроса
            data = response.json()

            if "values" not in data or not data["values"]:
                logger.error("[DB] Ошибка: данные не найдены")
                return

            result = []
            for row in data["values"]:
                # Проверяем, что в строке есть хотя бы 2 элемента
                if len(row) >= 2:
                    question_answer = {
                        'question': row[0],  # Первый элемент строки - это вопрос
                        'answer_example': row[1]  # Второй элемент строки - это ответ
                    }
                    result.append(question_answer)
                elif len(row) == 1:
                    # Если есть только вопрос без ответа
                    question_answer = {
                        'question': row[0],
                        'answer_example': ''
                    }
                    result.append(question_answer)

            return json.dumps(result, ensure_ascii=False, indent=2)
        except httpx.RequestError as e:
            logger.error(f"[DB] Ошибка при запросе: {e}")
            return None