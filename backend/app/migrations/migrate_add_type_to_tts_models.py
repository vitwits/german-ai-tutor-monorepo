#!/usr/bin/env python3
"""
Додає колонку 'type' до таблиці 'tts_models'
"""
import asyncio
import os
import sys
from sqlalchemy import text

# Add the app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.database import engine


async def main():
    async with engine.begin() as conn:
        try:
            # Перевіримо чи колонка вже існує
            result = await conn.execute(
                text("PRAGMA table_info(tts_models)")
            )
            columns = [row[1] for row in result.fetchall()]
            
            if 'type' in columns:
                print("✅ Колонка 'type' вже існує в таблиці 'tts_models'")
                return
            
            # Додаємо колонку з default значенням 'TTS'
            await conn.execute(
                text("ALTER TABLE tts_models ADD COLUMN type VARCHAR DEFAULT 'TTS' NOT NULL")
            )
            await conn.commit()
            print("✅ Успішно додана колонка 'type' до таблиці 'tts_models' з default значенням 'TTS'")
            
        except Exception as e:
            print(f"❌ Помилка: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
