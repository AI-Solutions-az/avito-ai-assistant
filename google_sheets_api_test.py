#!/usr/bin/env python3
"""
Быстрый тест парсера - минимальная версия
Использование: python quick_test.py [URL]
"""

import asyncio
import sys
import os

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.services.google_sheets_api import fetch_google_sheet_stock


async def quick_test(url=None):
    """Быстрый тест одного URL"""

    if not url:
        # URL из вашего примера с несколькими ID в одной ячейке
        test_urls = ["https://www.avito.ru/moskva/odezhda_obuv_aksessuary/letniy_kostyum_fred_perry_7352757129"
        ]

        print("🧪 Тестируем URL с множественными ID в ячейке:")
        for test_url in test_urls:
            print(f"\n📍 {test_url}")
            result = await fetch_google_sheet_stock(test_url)
            if result:
                print("✅ Найдено!")
                await asyncio.sleep(10)
                print(result)
            else:
                print("❌ Не найдено")
            print("-" * 50)
    else:
        print(f"🔍 Тестируем: {url}")
        result = await fetch_google_sheet_stock(url)

        if result:
            print("\n✅ Результат:")
            print(result)

            # Сохраняем в файл
            filename = "test_result.json"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"\n💾 Сохранено в {filename}")
        else:
            print("\n❌ Данные не найдены")


if __name__ == "__main__":
    # Загружаем переменные окружения
    from dotenv import load_dotenv

    load_dotenv()

    # Проверяем аргументы командной строки
    url = sys.argv[1] if len(sys.argv) > 1 else None

    # Запускаем тест
    asyncio.run(quick_test(url))