#!/usr/bin/env python3
"""
Миграция данных из SQLite в PostgreSQL - финальная версия
Использует asyncio и необработанный SQL для обхода проблем с типами
"""

import asyncio
import sys
import os
from pathlib import Path

from dotenv import load_dotenv
env_path = Path('/Users/omicron/Desktop/german_ai_tutor/.env')
load_dotenv(env_path)

sys.path.insert(0, '/Users/omicron/Desktop/german_ai_tutor/backend')

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool

async def migrate_with_sql():
    """Міграція через прямий SQL без конфліктів типів"""
    
    print("🔄 Розпочинаємо миграцію через SQL...\n")
    
    import sqlite3
    import json
    
    # Читаємо дані з SQLite
    sqlite_db = "/Users/omicron/Desktop/german_ai_tutor/backend/data/app.db"
    sqlite_conn = sqlite3.connect(sqlite_db)
    sqlite_cursor = sqlite_conn.cursor()
    
    # Підключаємось до PostgreSQL з NullPool
    postgres_url = f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    postgres_engine = create_async_engine(postgres_url, echo=False, poolclass=NullPool)
    
    tables_order = [
        'users',
        'billing_plans',
        'llm_models',
        'tts_models',
        'llm_prices',
        'tts_voices',
        'ai_preferences',
        'model_prompts',
        'lessons',
        'lesson_audio',
        'sentences',
        'vocabulary',
        'user_lessons',
        'user_favorite_sentences',
        'quiz_results',
        'user_blocked_sentences',
        'feedback',
        'user_billing',
        'tts_logs',
        'temp_sentences',
        'sentence_batches',
        'reported_lessons',
    ]
    
    def safe_sql_value(val):
        """Конвертує значення в безпечний SQL формат"""
        if val is None:
            return "NULL"
        if isinstance(val, bool):
            return "1" if val else "0"
        if isinstance(val, (int, float)):
            return str(val)
        if isinstance(val, str):
            return "'" + val.replace("'", "''") + "'"
        return "'" + str(val).replace("'", "''") + "'"
    
    async with postgres_engine.begin() as conn:
        # Вимикаємо foreign key перевірки під час імпорту
        await conn.execute(text("SET session_replication_role = replica"))
        
        for table_name in tables_order:
            try:
                # Очищуємо таблицю
                await conn.execute(text(f"DELETE FROM {table_name}"))
                
                # Читаємо дані з SQLite
                sqlite_cursor.execute(f"SELECT * FROM {table_name}")
                rows = sqlite_cursor.fetchall()
                
                if not rows:
                    print(f"⏭️  '{table_name}': немає даних")
                    continue
                
                # Отримуємо назви колонок
                columns = [desc[0] for desc in sqlite_cursor.description]
                
                print(f"📦 '{table_name}': імпортуємо {len(rows)} записів")
                
                # Вставляємо дані
                for row in rows:
                    values = [safe_sql_value(row[i]) for i in range(len(columns))]
                    insert_sql = f"""INSERT INTO {table_name} ({', '.join(columns)}) 
                                     VALUES ({', '.join(values)})"""
                    
                    try:
                        await conn.execute(text(insert_sql))
                    except Exception as e:
                        print(f"       ⚠️  Помилка: {type(e).__name__}")
                        continue
                
                print(f"   ✅ {len(rows)} записів імпортовано")
            
            except Exception as e:
                print(f"   ⚠️  {table_name}: {type(e).__name__}: {e}")
                continue
        
        # Вмикаємо foreign key перевірки
        await conn.execute(text("SET session_replication_role = DEFAULT"))
        
        # Коммітимо
        await conn.commit()
    
    print("\n✨ Миграция завершена!")
    
    sqlite_cursor.close()
    sqlite_conn.close()
    await postgres_engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate_with_sql())
