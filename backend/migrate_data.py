#!/usr/bin/env python3
"""
Міграція даних з SQLite в PostgreSQL
"""

import asyncio
import sys
import os
from pathlib import Path

# Завантажуємо .env
from dotenv import load_dotenv
env_path = Path('/Users/omicron/Desktop/german_ai_tutor/.env')
load_dotenv(env_path)

# Додаємо backend до path
sys.path.insert(0, '/Users/omicron/Desktop/german_ai_tutor/backend')

from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

async def migrate_data():
    """Мігрує дані з SQLite в PostgreSQL"""
    
    print("🔄 Розпочинаємо міграцію даних з SQLite → PostgreSQL...\n")
    
    # Підключаємось до SQLite (читання)
    sqlite_url = "sqlite+aiosqlite:///./data/app.db"
    sqlite_engine = create_async_engine(sqlite_url, echo=False)
    SQLiteSession = sessionmaker(sqlite_engine, class_=AsyncSession, expire_on_commit=False)
    
    # Підключаємось до PostgreSQL (запис)
    postgres_url = f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    postgres_engine = create_async_engine(postgres_url, echo=False)
    PostgresSession = sessionmaker(postgres_engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        # Імпортуємо моделі
        from app import models
        
        # Список таблиць для міграції (в порядку залежностей)
        tables_to_migrate = [
            ('users', models.User),
            ('billing_plans', models.BillingPlan),
            ('llm_models', models.LLMModel),
            ('tts_models', models.TTSModel),
            ('llm_prices', models.LLMPrice),
            ('tts_voices', models.TTSVoice),
            ('ai_preferences', models.AIPreference),
            ('model_prompts', models.ModelPrompt),
            ('lessons', models.Lesson),
            ('lesson_audio', models.LessonAudio),
            ('sentences', models.Sentence),
            ('vocabulary', models.Vocabulary),
            ('user_lessons', models.UserLesson),
            ('user_favorite_sentences', models.UserFavoriteSentence),
            ('quiz_results', models.QuizResult),
            ('user_blocked_sentences', models.UserBlockedSentence),
            ('feedback', models.Feedback),
            ('user_billing', models.UserBilling),
            ('tts_logs', models.TTSLog),
            ('temp_sentences', models.TempSentence),
            ('sentence_batches', models.SentenceBatch),
            ('reported_lessons', models.ReportedLesson),
        ]
        
        async with SQLiteSession() as sqlite_session:
            async with PostgresSession() as postgres_session:
                
                for table_name, model_class in tables_to_migrate:
                    try:
                        # Читаємо дані з SQLite
                        result = await sqlite_session.execute(select(model_class))
                        rows = result.scalars().all()
                        
                        if rows:
                            print(f"📦 Мігруємо таблицю '{table_name}': {len(rows)} записів")
                            
                            # Додаємо дані в PostgreSQL
                            for row in rows:
                                postgres_session.add(row)
                            
                            # Фіксимо зміни
                            await postgres_session.commit()
                            print(f"   ✅ {len(rows)} записів успішно імпортовано")
                        else:
                            print(f"⏭️  Таблиця '{table_name}': немає даних")
                    
                    except Exception as e:
                        print(f"   ⚠️  Помилка при міграції '{table_name}': {e}")
                        await postgres_session.rollback()
                        continue
        
        print("\n✨ Міграція завершена успішно!")
        
    except Exception as e:
        print(f"❌ Критична помилка: {e}")
        sys.exit(1)
    
    finally:
        await sqlite_engine.dispose()
        await postgres_engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate_data())
