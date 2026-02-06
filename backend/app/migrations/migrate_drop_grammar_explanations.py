"""
Migration: Drop grammar_explanations table

This migration removes the grammar_explanations table and all grammar explanation functionality.
Grammar explanation feature has been deprecated from the application.

Created: 2026-02-02
"""

import asyncio
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///./app.db')

async def migrate():
    """Drop grammar_explanations table if it exists"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        # Check if table exists
        inspector = inspect(conn.sync_engine)
        tables = inspector.get_table_names()
        
        if 'grammar_explanations' in tables:
            print("Dropping grammar_explanations table...")
            await conn.execute(text("DROP TABLE IF EXISTS grammar_explanations"))
            print("✅ grammar_explanations table dropped successfully")
        else:
            print("ℹ️  grammar_explanations table does not exist, skipping...")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
    print("\n✅ Migration completed!")
