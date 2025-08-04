import httpx
import json
import re
from app.services.logs import logger
from app.config import RANGE, SPREADSHEET_ID, API_KEY


async def extract_ad_id_from_url(ad_url):  # ✅ ASYNC
    """
    Извлекает ID объявления из URL.
    """
    match = re.search(r'_(\d+)$', ad_url)
    if match:
        return match.group(1)
    match = re.search(r'/(\d{7,})(?:/|$)', ad_url)
    if match:
        return match.group(1)
    return None


async def parse_ids_from_cell(cell_value):  # ✅ ASYNC
    """
    Извлекает все ID из ячейки, где ID могут быть разделены запятыми или пробелами.
    """
    if not cell_value:
        return []

    cell_value = str(cell_value).strip()
    ids = re.split(r'[,\s]+', cell_value)
    valid_ids = [id_str.strip() for id_str in ids if id_str.strip().isdigit()]
    return valid_ids


async def get_all_sheet_names():  # ✅ ASYNC
    """
    Получает список всех листов в Google таблице
    """
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}?key={API_KEY}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            sheets = []
            for sheet in data.get('sheets', []):
                sheet_name = sheet['properties']['title']
                sheets.append(sheet_name)
                logger.info(f"Найден лист: {sheet_name}")

            return sheets
        except Exception as e:
            logger.error(f"Ошибка при получении списка листов: {e}")
            return []


async def search_product_in_sheet(ad_id, sheet_name):  # ✅ ASYNC
    """
    Ищет товар в конкретном листе
    """
    logger.info(f"Поиск товара с ID {ad_id} в листе: {sheet_name}")

    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{sheet_name}!{RANGE}?majorDimension=ROWS&key={API_KEY}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            if "values" not in data or not data["values"]:
                logger.info(f"Данные не найдены в листе {sheet_name}")
                return None

            rows = data["values"]

            # Ищем заголовки (строка с "Id" в первой колонке)
            headers_row_index = None
            for i, row in enumerate(rows):
                if row and row[0] == "Id":
                    headers_row_index = i
                    break

            if headers_row_index is None:
                logger.info(f"Заголовки не найдены в листе {sheet_name}")
                return None

            headers = rows[headers_row_index]

            # Ищем строку с нужным ID
            id_column_index = 0  # Колонка A
            found_row_index = None

            for i in range(headers_row_index + 1, len(rows)):
                row = rows[i]
                if len(row) > id_column_index and row[id_column_index]:
                    # Извлекаем все ID из ячейки
                    ids_in_cell = await parse_ids_from_cell(row[id_column_index])  # ✅ await
                    # Проверяем, есть ли наш ID среди них
                    if ad_id in ids_in_cell:
                        logger.info(f"Товар с ID {ad_id} найден в листе {sheet_name}, строка {i + 1}")
                        found_row_index = i
                        break

            if found_row_index is None:
                logger.info(f"Товар с ID {ad_id} не найден в листе {sheet_name}")
                return None

            # Возвращаем найденные данные
            return {
                'sheet_name': sheet_name,
                'headers': headers,
                'found_row_index': found_row_index,
                'rows': rows
            }

        except Exception as e:
            logger.error(f"Ошибка при поиске в листе {sheet_name}: {e}")
            return None


async def fetch_google_sheet_stock(ad_url):  # ✅ ASYNC
    """
    Поиск товара по всем листам Google таблицы
    Возвращает данные о товаре и его доступности
    """
    # Извлекаем ID из URL
    ad_id = await extract_ad_id_from_url(ad_url)  # ✅ await
    if not ad_id:
        logger.error(f"Не удалось извлечь ID из URL: {ad_url}")
        return None

    logger.info(f"Ищем объявление с ID: {ad_id}")

    # Получаем список всех листов
    sheet_names = await get_all_sheet_names()  # ✅ await
    if not sheet_names:
        logger.error("Не удалось получить список листов")
        return None

    # Ищем товар во всех листах
    for sheet_name in sheet_names:
        # Пропускаем служебные листы (только knowledge_base)
        if sheet_name.lower() == 'knowledge_base':  # ✅ УПРОЩЕНО
            logger.info(f"Пропускаем служебный лист: {sheet_name}")
            continue

        result = await search_product_in_sheet(ad_id, sheet_name)  # ✅ await
        if result:
            logger.info(f"Товар найден в категории: {sheet_name}")
            return await parse_product_from_sheet_data(result, ad_url)  # ✅ await

    logger.error(f"Товар с ID {ad_id} не найден ни в одном листе")
    return None


async def parse_product_from_sheet_data(sheet_data, ad_url):  # ✅ ASYNC
    """
    Парсит данные товара из найденного листа
    """
    try:
        sheet_name = sheet_data['sheet_name']
        headers = sheet_data['headers']
        rows = sheet_data['rows']
        found_row_index = sheet_data['found_row_index']

        # Извлекаем все строки для данного товара
        product_rows = []
        current_index = found_row_index

        # Получаем все ID из найденной строки
        found_ids = await parse_ids_from_cell(rows[found_row_index][0])  # ✅ await
        logger.info(f"ID в найденной строке: {found_ids}")

        while current_index < len(rows):
            row = rows[current_index]
            logger.info(f"Обрабатываем строку {current_index + 1}: {row[:5] if len(row) > 5 else row}")

            # Если строка пустая или начинается новый блок заголовков
            if not row or (row and row[0] == "Id"):
                logger.info("Встретили пустую строку или новый блок заголовков")
                break

            # Если встретили новый набор ID в колонке A (новый товар)
            if current_index > found_row_index and len(row) > 0 and row[0]:
                current_ids = await parse_ids_from_cell(row[0])  # ✅ await
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

        return await parse_stock_with_availability_only(headers, product_rows, ad_url, sheet_name)  # ✅ await

    except Exception as e:
        logger.error(f"Ошибка при парсинге данных из листа: {e}")
        return None


async def parse_stock_with_availability_only(headers, product_rows, ad_url, category):  # ✅ ASYNC
    """
    Парсинг информации о товаре с ответами только "Есть в наличии"/"Нет в наличии"
    """
    try:
        if not product_rows:
            logger.error("Нет данных для парсинга")
            return None

        # Функция для безопасного получения значения из списка
        async def safe_get(lst, index, default=''):  # ✅ ASYNC
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
            'category': category,  # Добавляем категорию товара (название листа)
            'name': await safe_get(first_row, 1),  # ✅ await
            'price': '',
            'description': await safe_get(first_row, description_index) if description_index else '',  # ✅ await
            'size_info': await safe_get(first_row, size_info_index) if size_info_index else '',  # ✅ await
            'payment_method': '',
            'delivery_method': '',
            'photo_ids': await safe_get(first_row, photo_ids_index) if photo_ids_index else '',  # ✅ await
            'stock': []
        }

        # Обрабатываем каждую строку с цветом
        for row in product_rows:
            color = await safe_get(row, 3)  # ✅ await - Цвет в колонке D (индекс 3)
            if not color:
                continue

            # Собираем информацию о размерах (колонки E-L, индексы 4-11)
            stock_item = {
                'color': color,
                'sizes': {}
            }

            # Размеры: динамически определяем из заголовков
            size_mapping = {}
            size_start_index = 4  # Начинаем с колонки E

            # Ищем где заканчиваются размеры
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
                    elif size_name == 'M' or size_name == 'М':
                        size_name = 'M'
                    # Остальные размеры остаются как есть: XS, S, L, XL

                    size_mapping[i] = size_name
                    logger.info(f"Найден размер '{header}' -> '{size_name}' в колонке {i}")
                elif header:
                    # Встретили не-размерную колонку, прекращаем поиск размеров
                    break

            if not size_mapping:
                logger.warning("Не найдены колонки с размерами, используем стандартный диапазон")
                for i in range(4, min(12, len(headers))):
                    if i < len(headers) and headers[i] and headers[i].strip():
                        size_mapping[i] = headers[i].strip()

            logger.info(f"Итоговая карта размеров: {size_mapping}")

            # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Вместо точного количества возвращаем только статус наличия
            for col_index, size_name in size_mapping.items():
                quantity = await safe_get(row, col_index, '0')  # ✅ await

                # Преобразуем в число, если это возможно
                try:
                    quantity = int(quantity) if quantity else 0
                except ValueError:
                    quantity = 0

                # ❗ ГЛАВНОЕ ОТЛИЧИЕ ОТ СТАРОЙ ВЕРСИИ:
                # Возвращаем только статус наличия
                stock_item['sizes'][size_name] = "Есть в наличии" if quantity > 0 else "Нет в наличии"

            # Подсчитываем общее количество для данного цвета (для внутренней логики)
            available_sizes = sum(1 for status in stock_item['sizes'].values() if status == "Есть в наличии")
            stock_item['has_available_sizes'] = available_sizes > 0

            # Добавляем все цвета (даже если нет в наличии)
            product['stock'].append(stock_item)

        # Добавляем сводную информацию
        product['has_stock'] = any(item['has_available_sizes'] for item in product['stock'])
        product['available_colors'] = [item['color'] for item in product['stock'] if item['has_available_sizes']]

        return json.dumps(product, ensure_ascii=False, indent=4)

    except Exception as e:
        logger.error(f'Ошибка при парсинге строки из документа: {e}')
        return None


async def get_knowledge_base():  # ✅ ASYNC
    """
    Получение информации из базы знаний (остается без изменений)
    """
    # Пытаемся найти лист с базой знаний
    knowledge_sheet_names = ['knowledge_base']

    for sheet_name in knowledge_sheet_names:
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{sheet_name}!{RANGE}?majorDimension=ROWS&key={API_KEY}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                if "values" not in data or not data["values"]:
                    logger.info(f"Данные не найдены в листе {sheet_name}")
                    continue

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

                logger.info(f"База знаний найдена в листе: {sheet_name}")
                return json.dumps(result, ensure_ascii=False, indent=2)

            except httpx.RequestError as e:
                logger.info(f"Лист {sheet_name} не найден или недоступен: {e}")
                continue
            except Exception as e:
                logger.error(f"Ошибка при обработке листа {sheet_name}: {e}")
                continue

    logger.warning("База знаний не найдена ни в одном из ожидаемых листов")
    return None
