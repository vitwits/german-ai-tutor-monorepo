"""
Міграція: Додати custom_title колонку до user_lessons таблиці.
Дозволяє кожному користувачу перейменовувати текст для себе.
"""

import asyncio
import sqlite3
from sqlalchemy.ext.asyncio import create_async_engine
from app.database import Base

async def migrate():
    DATABASE_URL = "sqlite+aiosqlite:///./app/data.db"
    engine = create_async_engine(DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Tables ensured")

    db_path = "./app/data.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(user_lessons)")
        columns = {row[1] for row in cursor.fetchall()}

        if 'custom_title' in columns:
            print("✅ Column 'custom_title' already exists")
        else:
            cursor.execute("ALTER TABLE user_lessons ADD COLUMN custom_title VARCHAR")
            conn.commit()
            print("✅ Column 'custom_title' added to user_lessons")

        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
