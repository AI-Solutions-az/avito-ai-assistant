import httpx
import json
from app.services.logs import logger
from app.config import RANGE, SPREADSHEET_ID, WAREHOUSE_SHEET_NAME, KNOWLEDGE_BASE_SHEET_NAME, API_KEY


async def fetch_google_sheet_stock(ad_url):
    '''
    Поиск строки с идентификатором объявления
    Парсинг строки
    Возврат json'а с данными по товару и его доступности
    :param ad_url:
    :return:
    '''
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

            # Ищем строку с нужным URL
            ad_column_index = 1  # Колонка B
            found_row_index = None

            for i in range(headers_row_index + 1, len(rows)):
                row = rows[i]
                if len(row) > ad_column_index and row[ad_column_index] == ad_url:
                    logger.info(f"Объявление найдено в строке {i + 1}")
                    found_row_index = i
                    break

            if found_row_index is None:
                logger.error("Ошибка: объявление не найдено")
                return None

            # Извлекаем все строки для данного товара
            product_rows = []
            current_index = found_row_index

            while current_index < len(rows):
                row = rows[current_index]

                # Если строка пустая или начинается новый блок заголовков
                if not row or (row and row[0] == "Id"):
                    break

                # Если встретили новый URL в колонке B (новый товар)
                if current_index > found_row_index and len(row) > ad_column_index and row[ad_column_index] and row[
                    ad_column_index] != ad_url:
                    break

                # Добавляем строку только если есть данные о цвете
                if len(row) > 4 and row[4]:  # Проверяем наличие цвета
                    product_rows.append(row)

                current_index += 1

            if not product_rows:
                logger.error("Ошибка: данные о товаре не найдены")
                return None

            return parse_stock(headers, product_rows)

        except httpx.RequestError as e:
            logger.error(f"Ошибка при запросе: {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP ошибка: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")
            return None


def parse_stock(headers, product_rows):
    '''
    Парсинг информации о найденной по идентификатору строке
    :param headers: Заголовки колонок
    :param product_rows: Строки с данными о товаре
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

        product = {
            'id': safe_get(first_row, 1),
            'name': safe_get(first_row, 2),
            'price': safe_get(first_row, 10),  # Цена в колонке K (индекс 10)
            'description': safe_get(first_row, 11),  # Описание в колонке L
            'size_info': safe_get(first_row, 12),  # Размерная сетка в колонке M
            'payment_method': safe_get(first_row, 13),  # Способ оплаты в колонке N
            'delivery_method': safe_get(first_row, 14),  # Способ доставки в колонке O
            'photo_ids': safe_get(first_row, 15),  # ID фотографий в колонке P
            'stock': []
        }

        # Обрабатываем каждую строку с цветом
        for row in product_rows:
            color = safe_get(row, 4)  # Цвет в колонке E
            if not color:
                continue

            # Собираем информацию о размерах (колонки F-K, индексы 5-10)
            stock_item = {
                'color': color,
                'sizes': {}
            }

            # Размеры: S, M, L, XL, XXL (2XL), XXXL (3XL)
            size_mapping = {
                5: 'S',
                6: 'M',
                7: 'L',
                8: 'XL',
                9: 'XXL (2XL)',
                10: 'XXXL (3XL)'
            }

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