#!/usr/bin/env python3
"""
Скрипт для створення всіх таблиць в PostgreSQL
"""

import asyncio
import sys
import os
from pathlib import Path

# Завантажуємо .env перед імпортом app
from dotenv import load_dotenv
env_path = Path('/Users/omicron/Desktop/german_ai_tutor/.env')
load_dotenv(env_path)

print(f"📂 Завантажено .env з: {env_path}")
print(f"🔧 DB_TYPE={os.getenv('DB_TYPE')}")

# Додаємо backend до path
sys.path.insert(0, '/Users/omicron/Desktop/german_ai_tutor/backend')

from app.database import engine, Base
from app import models  # Імпортуємо моделі, щоб вони були зареєстровані

async def create_tables():
    """Створює всі таблиці в базі даних"""
    
    print("🔄 Створюємо таблиці в PostgreSQL...")
    
    try:
        # Створюємо всі таблиці
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("✅ Всі таблиці успішно створені!")
        print("\n📊 Таблиці:")
        
        # Перевіримо створені таблиці
        async with engine.begin() as conn:
            from sqlalchemy import text
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """))
            
            tables = result.fetchall()
            for table in tables:
                print(f"   ✓ {table[0]}")
        
        await engine.dispose()
        
    except Exception as e:
        print(f"❌ Помилка: {e}")
        await engine.dispose()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(create_tables())
