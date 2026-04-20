#!/usr/bin/env python3
"""
Скрипт для перевірки даних в PostgreSQL після міграції
"""

import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text, select
from sqlalchemy.orm import DeclarativeBase

# Конфіг PostgreSQL
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "german_ai_tutor")

DATABASE_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

async def check_migration():
    """Перевіримо дані в PostgreSQL"""
    
    print("🔌 Підключаємось до PostgreSQL...")
    print(f"📍 {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
    
    try:
        engine = create_async_engine(DATABASE_URL, echo=False)
        
        async with engine.begin() as conn:
            print("✅ Успішно підключено до PostgreSQL!\n")
            
            # Перевіримо таблиці
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """))
            
            tables = result.fetchall()
            print(f"📊 Знайдено {len(tables)} таблиць:")
            for table in tables:
                print(f"   - {table[0]}")
            
            # Перевіримо кількість записів у ключових таблицях
            print("\n📈 Кількість записів:")
            
            key_tables = ['users', 'lessons', 'vocabulary', 'model_prompts']
            for table in key_tables:
                try:
                    result = await conn.execute(text(f"SELECT COUNT(*) FROM {table};"))
                    count = result.scalar()
                    print(f"   - {table}: {count} записів")
                except Exception as e:
                    print(f"   - {table}: ⚠️ помилка ({type(e).__name__})")
            
            print("\n✨ Міграція успішна!")
        
        await engine.dispose()
        
    except Exception as e:
        print(f"❌ Помилка підключення: {e}")
        print(f"\nПеревірте:")
        print(f"  1. Docker PostgreSQL запущений: docker-compose ps")
        print(f"  2. Конфіг .env правильний")
        print(f"  3. Скрипт міграції був запущений")

if __name__ == "__main__":
    asyncio.run(check_migration())
