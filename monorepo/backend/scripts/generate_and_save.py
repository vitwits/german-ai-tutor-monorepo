#!/usr/bin/env python3
"""
Обгортка для generate_sentences.py що зберігає результати в БД замість CSV
"""
import os
import sys
import json
import csv
import time
import random
import datetime
import re
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Налаштування шляхів
BACKEND_DIR = Path(__file__).parent.parent  # /monorepo/backend
BASE_DIR = BACKEND_DIR.parent  # /monorepo
load_dotenv(BASE_DIR / ".env")

# Налаштування Google Cloud credentials
google_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service-account.json")
if not Path(google_creds).is_absolute():
    google_creds = BASE_DIR / google_creds
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(google_creds)

# Додаємо app в path
sys.path.insert(0, str(BACKEND_DIR))

from app.models import SentenceBatch, TempSentence, Base
from app.database import DATABASE_URL

# ВАЖЛИВО: Виконуємо код з generate_sentences.py
# Це потрібно для CEFR_GUIDELINES та функції generate_batch()
SCRIPTS_DIR = Path(__file__).parent
with open(SCRIPTS_DIR / "generate_sentences.py", 'r', encoding='utf-8') as f:
    script_code = f.read()
    # Отримуємо все до def main()
    config_code = script_code.split("def main():")[0]
    # Виконуємо конфіги в локальному namespace
    exec(config_code)

async def save_sentences_to_db(batch_id, sentences):
    """Зберігає тимчасові речення в БД"""
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session() as db:
        # Додаємо речення до батча (як тимчасові)
        for s in sentences:
            temp_sentence = TempSentence(
                batch_id=batch_id,
                de=s.get('de', ''),
                uk=s.get('uk', ''),
                en=s.get('en', ''),
                topic=s.get('topic', '')
            )
            db.add(temp_sentence)
        
        # Оновлюємо батч
        result = await db.execute(
            select(SentenceBatch).where(SentenceBatch.id == batch_id)
        )
        batch = result.scalar_one_or_none()
        
        if batch:
            batch.status = "text_ready"
            batch.processed_count = len(sentences)
        
        await db.commit()
        print(f"✓ Saved {len(sentences)} temp sentences to batch {batch_id}")

async def main():
    if len(sys.argv) < 3:
        print("Usage: python generate_and_save.py <batch_id> <level> <count>")
        sys.exit(1)

    try:
        batch_id = int(sys.argv[1])
    except ValueError:
        print("Error: Batch ID must be a number.")
        sys.exit(1)

    level = sys.argv[2].upper()
    try:
        total_count = int(sys.argv[3])
    except ValueError:
        print("Error: Count must be a number.")
        sys.exit(1)

    if level not in CEFR_GUIDELINES:
        print(f"Warning: Level {level} not found.")
        level = "A2"

    available_topics = LEVEL_RULES.get(level, A2_TOPICS)
    
    print(f"\n--- Generating {total_count} {level} sentences for batch {batch_id} ---\n")

    BATCH_SIZE = 20
    generated_count = 0
    all_sentences = []
    
    while generated_count < total_count:
        current_batch_size = min(BATCH_SIZE, total_count - generated_count)
        
        if len(available_topics) >= current_batch_size:
            batch_topics = random.sample(available_topics, current_batch_size)
        else:
            batch_topics = random.choices(available_topics, k=current_batch_size)
        
        print(f"Generating batch {generated_count + 1}-{generated_count + current_batch_size}...")
        
        sentences = generate_batch(level, current_batch_size, batch_topics)
        
        if not sentences:
            print("Failed. Retrying in 2 seconds...")
            time.sleep(2)
            continue
        
        all_sentences.extend(sentences)
        generated_count += len(sentences)
        print(f"  → {len(sentences)} sentences")
        time.sleep(1)

    print(f"\n✓ Generated {generated_count} sentences")
    print(f"Saving to database...")
    
    await save_sentences_to_db(batch_id, all_sentences)
    
    print(f"✓ Done!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
