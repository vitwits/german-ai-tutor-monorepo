#!/usr/bin/env python3
"""
Миграция через asyncpg - исправленная версия
"""

import asyncio
import sys
import os
from pathlib import Path
import sqlite3
from datetime import datetime

from dotenv import load_dotenv
env_path = Path('/Users/omicron/Desktop/german_ai_tutor/.env')
load_dotenv(env_path)

async def migrate():
    """Міграція з використанням asyncpg"""
    
    print("🔄 Розпочинаємо миграцію через asyncpg...\n")
    
    import asyncpg
    
    # Підключаємось до PostgreSQL
    conn = await asyncpg.connect(
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        database=os.getenv('POSTGRES_DB'),
        host=os.getenv('POSTGRES_HOST'),
        port=int(os.getenv('POSTGRES_PORT')),
    )
    
    # Читаємо з SQLite
    sqlite_db = "/Users/omicron/Desktop/german_ai_tutor/backend/data/app.db"
    sqlite_conn = sqlite3.connect(sqlite_db)
    sqlite_cursor = sqlite_conn.cursor()
    
    tables_order = [
        'users', 'billing_plans', 'llm_models', 'tts_models', 'llm_prices',
        'tts_voices', 'ai_preferences', 'model_prompts', 'lessons', 'lesson_audio',
        'sentences', 'vocabulary', 'user_lessons', 'user_favorite_sentences',
        'quiz_results', 'user_blocked_sentences', 'feedback', 'user_billing',
        'tts_logs', 'temp_sentences', 'sentence_batches', 'reported_lessons',
    ]
    
    try:
        # Вимикаємо foreign key перевірки та тригери
        await conn.execute("ALTER TABLE users DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE billing_plans DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE llm_models DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE tts_models DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE llm_prices DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE tts_voices DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE ai_preferences DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE model_prompts DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE lessons DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE lesson_audio DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE sentences DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE vocabulary DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE user_lessons DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE user_favorite_sentences DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE quiz_results DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE user_blocked_sentences DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE feedback DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE user_billing DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE tts_logs DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE temp_sentences DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE sentence_batches DISABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE reported_lessons DISABLE TRIGGER ALL")
        
        for table_name in tables_order:
            try:
                # Очищуємо таблицю
                await conn.execute(f"DELETE FROM {table_name}")
                
                # Читаємо дані з SQLite
                sqlite_cursor.execute(f"SELECT * FROM {table_name}")
                rows = sqlite_cursor.fetchall()
                
                if not rows:
                    print(f"⏭️  '{table_name}': немає даних")
                    continue
                
                columns = [desc[0] for desc in sqlite_cursor.description]
                
                # Вставляємо дані
                print(f"📦 '{table_name}': імпортуємо {len(rows)} записів", end=" ")
                
                count = 0
                last_error = None
                for i, row in enumerate(rows):
                    try:
                        # Конвертуємо типи для asyncpg
                        converted_row = []
                        for j, value in enumerate(row):
                            col_name = columns[j]
                            
                            # Конвертуємо datetime рядки
                            if value is not None and isinstance(value, str):
                                # Спробуємо розпізнати datetime за паттерном
                                if ' ' in value and ':' in value and '-' in value:
                                    # Виглядає як datetime
                                    try:
                                        # Спробуємо стандартні формати
                                        converted_row.append(datetime.fromisoformat(value.replace('Z', '+00:00')))
                                    except ValueError:
                                        converted_row.append(value)
                                else:
                                    converted_row.append(value)
                            # Конвертуємо boolean значення
                            elif isinstance(value, int) and col_name in [
                                'is_active', 'is_completed', 'is_hidden', 'is_blocked',
                                'is_correct', 'is_admin', 'is_speaking_allowed'
                            ]:
                                converted_row.append(bool(value))
                            else:
                                converted_row.append(value)
                        
                        placeholders = ', '.join([f'${j+1}' for j in range(len(columns))])
                        insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
                        await conn.execute(insert_sql, *converted_row)
                        count += 1
                    except Exception as e:
                        # Запомним последнюю ошибку для отладки
                        if i == 0:
                            last_error = e
                        continue
                
                if last_error and count == 0:
                    print(f"❌ Ошибка: {str(last_error)[:80]}")
                else:
                    print(f"✅ {count} записів")
            
            except Exception as e:
                print(f"   ⚠️  Помилка: {type(e).__name__}: {str(e)[:50]}")
                continue
        
        print("\n✨ Миграция завершена!")
        
        # Вмикаємо тригери
        await conn.execute("ALTER TABLE users ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE billing_plans ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE llm_models ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE tts_models ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE llm_prices ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE tts_voices ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE ai_preferences ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE model_prompts ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE lessons ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE lesson_audio ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE sentences ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE vocabulary ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE user_lessons ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE user_favorite_sentences ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE quiz_results ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE user_blocked_sentences ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE feedback ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE user_billing ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE tts_logs ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE temp_sentences ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE sentence_batches ENABLE TRIGGER ALL")
        await conn.execute("ALTER TABLE reported_lessons ENABLE TRIGGER ALL")
        
    finally:
        await conn.close()
        sqlite_cursor.close()
        sqlite_conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
