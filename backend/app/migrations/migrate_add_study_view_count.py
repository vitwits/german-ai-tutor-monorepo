"""
Міграція: Додати study_view_count колонку до vocabulary таблиці.
"""

import asyncio
import sqlite3
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Vocabulary

async def migrate():
    # SQLite DATABASE URL
    DATABASE_URL = "sqlite+aiosqlite:///./app/data.db"
    
    # Create engine with asyncio
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    # 1. Create the table if it doesn't exist
    async with engine.begin() as conn:
        print("Creating all tables (if not exist)...")
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Tables ensured")
    
    # 2. Check if column already exists using raw SQLite
    db_path = "./app/data.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get table info
        cursor.execute("PRAGMA table_info(vocabulary)")
        columns = {row[1] for row in cursor.fetchall()}
        
        if 'study_view_count' in columns:
            print("✅ Column 'study_view_count' already exists")
        else:
            # Add column with default value 0
            cursor.execute("ALTER TABLE vocabulary ADD COLUMN study_view_count INTEGER DEFAULT 0")
            conn.commit()
            print("✅ Column 'study_view_count' added successfully")
        
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
