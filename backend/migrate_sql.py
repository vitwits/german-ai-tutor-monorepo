#!/usr/bin/env python3
"""
Миграция данных из SQLite в PostgreSQL (SQL-level)
"""

import asyncio
import sys
import os
from pathlib import Path

# Load .env
from dotenv import load_dotenv
env_path = Path('/Users/omicron/Desktop/german_ai_tutor/.env')
load_dotenv(env_path)

sys.path.insert(0, '/Users/omicron/Desktop/german_ai_tutor/backend')

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

async def migrate_data():
    """Мігрує дані на рівні SQL"""
    
    print("🔄 Розпочинаємо миграцію даних із SQLite → PostgreSQL (SQL-level)...\n")
    
    # Читаємо дані з SQLite через pyodbc/subprocess
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
    
    try:
        async with postgres_engine.begin() as conn:
            for table_name in tables:
                try:
                    # Отримаємо дані з SQLite
                    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
                    rows = sqlite_cursor.fetchall()
                    
                    if not rows:
                        print(f"⏭️  '{table_name}': немає даних")
                        continue
                    
                    # Отримуємо назви колонок
                    columns = [description[0] for description in sqlite_cursor.description]
                    
                    print(f"📦 '{table_name}': імпортуємо {len(rows)} записів")
                    
                    # Вставляємо дані в PostgreSQL
                    for row in rows:
                        # Формуємо INSERT запит
                        values = []
                        for col_name in columns:
                            val = row[col_name]
                            if val is None:
                                values.append("NULL")
                            elif isinstance(val, bool):
                                values.append("true" if val else "false")
                            elif isinstance(val, str):
                                # Екранування одинарних лапок
                                val_escaped = val.replace("'", "''")
                                values.append(f"'{val_escaped}'")
                            else:
                                values.append(str(val))
                        
                        insert_sql = f"""
                            INSERT INTO {table_name} ({', '.join(columns)})
                            VALUES ({', '.join(values)})
                            ON CONFLICT DO NOTHING
                        """
                        
                        try:
                            await conn.execute(text(insert_sql))
                        except Exception as e:
                            # Спробуємо без ON CONFLICT
                            insert_sql = f"""
                                INSERT INTO {table_name} ({', '.join(columns)})
                                VALUES ({', '.join(values)})
                            """
                            await conn.execute(text(insert_sql))
                    
                    print(f"   ✅ {len(rows)} записів успішно імпортовано")
                
                except Exception as e:
                    print(f"   ⚠️  Помилка при міграції '{table_name}': {type(e).__name__}: {e}")
                    continue
            
            #Commіт всех изменений
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
