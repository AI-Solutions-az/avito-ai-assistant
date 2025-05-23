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
            response.raise_for_status()  # Проверка успешности запроса
            data = response.json()

            if "values" not in data or not data["values"]:
                logger.error("Ошибка: данные не найдены")
                return

            headers = data["values"][0]  # Заголовки колонок
            rows = data["values"][0:]  # Данные (без заголовков)

            ad_column_index = 1  # Индекс колонки B (нумерация с 0)
            found_row_num = None

            for row_num, row in enumerate(rows, start=0):  # Начинаем с 2, так как 1-я строка — заголовки
                if len(row) > ad_column_index and row[ad_column_index] == ad_url:
                    logger.info(f"Объявление найдено в строке {row_num}")
                    found_row_num = row_num
                    break

            if found_row_num is None:
                logger.error("Ошибка: объявление не найдено")
                return

            extracted_rows = []
            for row in rows[found_row_num:]:  # -2, т.к. индексация с 0, а данные начинаются со 2-й строки
                if not row:  # Останов, если пустая строка
                    break
                extracted_rows.append(row)

            if not extracted_rows:
                logger.error("Ошибка: данные не найдены")
                return

            return await parse_stock(extracted_rows)

        except httpx.RequestError as e:
            logger.error(f"Ошибка при запросе: {e}")
            return None


async def parse_stock(data):
    '''
    Парсинг информации о найденной по идентификатору строке
    :param data:
    :return:
    '''
    try:
        headers = data[0]
        product_info = data[1]

        # Функция для безопасного получения значения из списка
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

        # Матрица цветов и размеров (столбцы с 5 по 11)
        for row in data[1:]:
            color = safe_get(row, 4)
            sizes = []

            # Собираем размеры для текущей строки
            for i in range(5, 11):
                sizes.append(safe_get(row, i, ''))

            # Убедимся, что у нас всегда 6 размеров
            while len(sizes) < 6:
                sizes.append('')

            product['current_stock'].append({
                'color': color,
                'sizes': {safe_get(headers, i, f'Size{i - 4}'): sizes[i - 5] for i in range(5, 11)}
            })

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