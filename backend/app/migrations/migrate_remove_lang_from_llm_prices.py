"""
Migration: Remove 'lang' column from llm_prices table

This migration removes the unused 'lang' column from the llm_prices table.

Usage:
    python migrate_remove_lang_from_llm_prices.py
"""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add the app directory to the path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir.parent))

from app.database import DATABASE_URL


async def migrate():
    """Remove lang column from llm_prices table"""
    engine = create_async_engine(DATABASE_URL)
    
    async with engine.begin() as conn:
        try:
            # Check if column exists before attempting to drop it
            result = await conn.execute(text("""
                PRAGMA table_info(llm_prices)
            """))
            columns = result.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'lang' in column_names:
                print("Removing 'lang' column from llm_prices table...")
                await conn.execute(text("""
                    ALTER TABLE llm_prices DROP COLUMN lang
                """))
                print("✅ Successfully removed 'lang' column from llm_prices")
            else:
                print("ℹ️ Column 'lang' does not exist in llm_prices table")
                
        except Exception as e:
            print(f"❌ Error during migration: {e}")
            raise
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
