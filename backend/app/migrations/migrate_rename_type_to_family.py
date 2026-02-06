#!/usr/bin/env python3
"""
Перейменовує колонку 'type' на 'family' у таблиці 'tts_models'
"""
import asyncio
from sqlalchemy import text
from app.database import engine


async def main():
    async with engine.begin() as conn:
        try:
            # Перевіримо чи колонка 'type' існує
            result = await conn.execute(
                text("PRAGMA table_info(tts_models)")
            )
            columns = {row[1]: row for row in result.fetchall()}
            
            if 'family' in columns:
                print("✅ Колонка 'family' вже існує в таблиці 'tts_models'")
                return
            
            if 'type' not in columns:
                print("❌ Колонка 'type' не знайдена в таблиці 'tts_models'")
                return
            
            # SQLite не підтримує прямого ALTER TABLE RENAME COLUMN для старих версій
            # Тому робимо це через тимчасову таблицю
            await conn.execute(text("""
                ALTER TABLE tts_models RENAME COLUMN type TO family
            """))
            await conn.commit()
            print("✅ Успішно перейменована колонка 'type' на 'family'")
            
        except Exception as e:
            print(f"❌ Помилка: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
