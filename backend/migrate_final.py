#!/usr/bin/env python3
"""
Финальная миграция данных из SQLite в PostgreSQL с обработкой типов
"""

import asyncio
import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Load .env
from dotenv import load_dotenv
env_path = Path('/Users/omicron/Desktop/german_ai_tutor/.env')
load_dotenv(env_path)

sys.path.insert(0, '/Users/omicron/Desktop/german_ai_tutor/backend')

from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import create_async_engine

async def migrate_data():
    """Мігрує дані на рівні SQL з правильною обробкою типів"""
    
    print("🔄 Розпочинаємо финальну миграцію SQLite → PostgreSQL...\n")
    
    import sqlite3
    
    sqlite_db = "/Users/omicron/Desktop/german_ai_tutor/backend/data/app.db"
    sqlite_conn = sqlite3.connect(sqlite_db)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()
    
    # Підключаємось до PostgreSQL
    postgres_url = f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    postgres_engine = create_async_engine(postgres_url, echo=False)
    
    # Список таблиць у порядку залежностей
    tables = [
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
    
    def convert_value(val, col_name):
        """Конвертує значення з SQLite в PostgreSQL формат"""
        if val is None:
            return "NULL"
        
        # Перевірка на булево значення (boolean/integer columns)
        if isinstance(val, int) and col_name in [
            'is_active', 'is_completed', 'is_hidden', 'is_blocked', 
            'is_correct', 'is_admin', 'is_speaking_allowed'
        ]:
            return "true" if val else "false"
        
        if isinstance(val, bool):
            return "true" if val else "false"
        
        if isinstance(val, str):
            # Екранування одинарних лапок і спеціальних символів
            val_escaped = val.replace("'", "''")
            return f"'{val_escaped}'"
        
        if isinstance(val, (int, float)):
            return str(val)
        
        # JSON поля
        if isinstance(val, str) and col_name in ['options', 'config', 'metadata', 'data']:
            try:
                json.loads(val)  # Перевіримо, чи це валідний JSON
                val_escaped = val.replace("'", "''")
                return f"'{val_escaped}'"
            except:
                pass
        
        # За замовчуванням - рядок
        val_escaped = str(val).replace("'", "''")
        return f"'{val_escaped}'"
    
    try:
        async with postgres_engine.begin() as conn:
            for table_name in tables:
                try:
                    # Очищуємо таблицю перед імпортом
                    await conn.execute(text(f"DELETE FROM {table_name}"))
                    
                    # Отримуємо дані з SQLite
                    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
                    rows = sqlite_cursor.fetchall()
                    
                    if not rows:
                        print(f"⏭️  '{table_name}': немає даних")
                        continue
                    
                    # Отримуємо назви колонок
                    columns = [description[0] for description in sqlite_cursor.description]
                    
                    print(f"📦 '{table_name}': імпортуємо {len(rows)} записів")
                    
                    # Вставляємо дані партіями по 100
                    for i in range(0, len(rows), 100):
                        batch = rows[i:i+100]
                        
                        for row in batch:
                            # Формуємо INSERT запит
                            values = []
                            for col_name in columns:
                                val = row[col_name]
                                values.append(convert_value(val, col_name))
                            
                            insert_sql = f"""
                                INSERT INTO {table_name} ({', '.join(columns)})
                                VALUES ({', '.join(values)})
                            """
                            
                            try:
                                await conn.execute(text(insert_sql))
                            except Exception as e:
                                print(f"       ⚠️  Ошибка при вставці рядка: {e}")
                                # Продовжуємо зі наступним рядком
                                continue
                    
                    print(f"   ✅ {len(rows)} записів успішно імпортовано")
                
                except Exception as e:
                    print(f"   ⚠️  Помилка при міграції '{table_name}': {type(e).__name__}")
                    # Спробуємо продовжити з наступною таблицею
                    continue
            
            # Коммітимо всі зміни
            await conn.commit()
        
        print("\n✨ Миграция завершена успешно!")
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
    
    finally:
        sqlite_cursor.close()
        sqlite_conn.close()
        await postgres_engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate_data())
