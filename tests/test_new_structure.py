#!/usr/bin/env python3
"""
Тест новой структуры таблицы с разделением на категории
"""

import asyncio
import sys
import os
import json

import pytest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.services.google_sheets_api import get_all_sheet_names, fetch_google_sheet_stock


async def explore_new_structure():
    """Исследуем новую структуру таблицы"""
    print("🔍 ИССЛЕДОВАНИЕ НОВОЙ СТРУКТУРЫ ТАБЛИЦЫ")
    print("=" * 60)
    print("🔗 https://docs.google.com/spreadsheets/d/16flBHTR0XouAsjqN6dtgh23LjlzQZMc92cIQExh-HzA/edit")
    print()

    # Получаем все листы
    sheets = await get_all_sheet_names()
    if not sheets:
        print("❌ Не удалось получить листы")
        return

    print(f"📋 НАЙДЕНО ЛИСТОВ: {len(sheets)}")
    for i, sheet in enumerate(sheets, 1):
        print(f"   {i}. {sheet}")

    # Определяем листы с товарами
    product_sheets = [s for s in sheets if s.lower() not in ['knowledge_base', 'база знаний', 'settings']]

    print(f"\n📦 ЛИСТЫ С ТОВАРАМИ: {len(product_sheets)}")
    for sheet in product_sheets:
        print(f"   • {sheet}")

    return product_sheets


async def test_category_search():
    """Тестируем поиск по категориям с вашими реальными ID"""
    print(f"\n🧪 ТЕСТ ПОИСКА ПО КАТЕГОРИЯМ")
    print("=" * 60)

    # Ваши реальные ID товаров
    test_ids = [
        "7380225838",  # Куртка polo ralph lauren
        "4600496946",  # Свитшот Lyle Scott
        "7352966820",  # Свитшот Lyle Scott (другой ID)
        "4600673225",  # Свитшот Lyle Scott (третий ID)
        "4569393163",  # Свитшот Lyle Scott (четвертый ID)
        "7256042815"  # Еще один товар
    ]

    results = {}

    for i, product_id in enumerate(test_ids, 1):
        test_url = f"https://www.avito.ru/moskva/odezhda_obuv_aksessuary/test_product_{product_id}"

        print(f"\n📍 ТЕСТ {i}: ID {product_id}")
        print(f"   URL: {test_url}")
        print("-" * 40)

        try:
            result = await fetch_google_sheet_stock(test_url)
            if result:
                data = json.loads(result)
                category = data.get('category', 'Не определена')
                name = data.get('name', 'Не указано')
                colors = len(data.get('stock', []))

                print(f"   ✅ НАЙДЕН!")
                print(f"   📁 Категория: {category}")
                print(f"   🏷️  Товар: {name}")
                print(f"   🎨 Цветов: {colors}")

                # Проверяем формат наличия
                availability_check = True
                for stock_item in data.get('stock', []):
                    for size, status in stock_item.get('sizes', {}).items():
                        if status not in ["Есть в наличии", "Нет в наличии"]:
                            availability_check = False
                            break

                print(f"   📊 Формат наличия: {'✅ Корректный' if availability_check else '❌ Ошибка'}")

                results[product_id] = {
                    'found': True,
                    'category': category,
                    'name': name,
                    'format_correct': availability_check
                }

                # Сохраняем результат для изучения
                with open(f"result_{product_id}.json", 'w', encoding='utf-8') as f:
                    f.write(result)
                print(f"   💾 Сохранено в result_{product_id}.json")

            else:
                print(f"   ❌ НЕ НАЙДЕН")
                results[product_id] = {'found': False}

        except Exception as e:
            print(f"   ❌ ОШИБКА: {e}")
            results[product_id] = {'found': False, 'error': str(e)}

        # Пауза между запросами
        await asyncio.sleep(1)

    return results


async def print_summary(results):
    """Выводим сводку результатов"""
    print(f"\n📊 СВОДКА РЕЗУЛЬТАТОВ")
    print("=" * 60)

    found_count = sum(1 for r in results.values() if r.get('found', False))
    total_count = len(results)

    print(f"🔍 Найдено товаров: {found_count}/{total_count}")

    # Группируем по категориям
    categories = {}
    for product_id, result in results.items():
        if result.get('found'):
            category = result.get('category', 'Неизвестно')
            if category not in categories:
                categories[category] = []
            categories[category].append(product_id)

    if categories:
        print(f"\n📁 ТОВАРЫ ПО КАТЕГОРИЯМ:")
        for category, ids in categories.items():
            print(f"   {category}: {len(ids)} товаров")
            for product_id in ids:
                product_name = results[product_id].get('name', 'Без названия')
                print(f"      • {product_id}: {product_name}")

    # Проверяем формат ответов
    format_correct = all(r.get('format_correct', True) for r in results.values() if r.get('found'))
    print(f"\n✅ Формат наличия корректен: {'Да' if format_correct else 'Нет'}")

    print(f"\n💡 СЛЕДУЮЩИЕ ШАГИ:")
    if found_count > 0:
        print(f"   ✅ Парсер работает с новой структурой!")
        print(f"   ✅ Товары находятся в разных категориях")
        print(f"   🔄 Можно запускать полноценные тесты")
    else:
        print(f"   ⚠️  Товары не найдены - проверьте:")
        print(f"      • Структуру новых листов")
        print(f"      • Правильность размещения ID товаров")
        print(f"      • Формат данных в листах")


async def main():
    """Главная функция"""
    print("🚀 ТЕСТ НОВОЙ СТРУКТУРЫ ТАБЛИЦЫ")
    print("=" * 80)

    # Исследуем структуру
    product_sheets = await explore_new_structure()

    if not product_sheets:
        print("❌ Нет листов с товарами для тестирования")
        return

    # Тестируем поиск
    results = await test_category_search()

    # Выводим сводку
    await print_summary(results)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    asyncio.run(main())
