#!/usr/bin/env python3
"""
Инициализация базы данных HotSpot Shop
Запустите на сервере: python3 init_db.py
"""
import os

print("🔄 Инициализация базы данных...")

# Импортируем Database - это автоматически создаст БД
from database import Database

db = Database()

# Проверяем категории
categories = db.get_categories()

print(f"\n✅ База данных успешно инициализирована!")
print(f"\n📊 Категории ({len(categories)}):")
for cat in categories:
    cashback = cat.get('cashback_rate', 3.0)
    print(f"  {cat['id']}: {cat['name']:30} - {cashback}% кешбека")

print("\n🎉 Готово! Можно запускать сервер.")

