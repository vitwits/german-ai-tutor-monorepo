"""
Міграція: Додати llm_cost, tts_cost та total_cost колонки до users таблиці.
"""

import asyncio
import sqlite3
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import User

async def migrate():
    # SQLite DATABASE URL - use the same path as in database.py
    import os
    DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/app.db"))
    DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"
    
    # Create engine with asyncio
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    # 1. Create the table if it doesn't exist
    async with engine.begin() as conn:
        print("Creating all tables (if not exist)...")
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Tables ensured")
    
    # 2. Check if columns already exist using raw SQLite
    db_path = DB_PATH
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get table info
        cursor.execute("PRAGMA table_info(users)")
        columns = {row[1] for row in cursor.fetchall()}
        
        # Add llm_cost column
        if 'llm_cost' in columns:
            print("✅ Column 'llm_cost' already exists")
        else:
            cursor.execute("ALTER TABLE users ADD COLUMN llm_cost REAL DEFAULT 0.0")
            print("✅ Column 'llm_cost' added successfully")
        
        # Add tts_cost column
        if 'tts_cost' in columns:
            print("✅ Column 'tts_cost' already exists")
        else:
            cursor.execute("ALTER TABLE users ADD COLUMN tts_cost REAL DEFAULT 0.0")
            print("✅ Column 'tts_cost' added successfully")
        
        # Add total_cost column
        if 'total_cost' in columns:
            print("✅ Column 'total_cost' already exists")
        else:
            cursor.execute("ALTER TABLE users ADD COLUMN total_cost REAL DEFAULT 0.0")
            print("✅ Column 'total_cost' added successfully")
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
