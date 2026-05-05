#!/usr/bin/env python3
"""
Migration script to add context translation columns to vocabulary table.
Adds ctx_ua and ctx_en columns for storing Ukrainian and English translations
of German context sentences.
"""

import asyncio
from sqlalchemy import text, inspect
from app.database import engine

async def migrate():
    """Add ctx_ua and ctx_en columns to vocabulary table"""
    
    async with engine.begin() as conn:
        try:
            # For SQLite, check existing columns using PRAGMA
            result = await conn.execute(text("PRAGMA table_info(vocabulary)"))
            columns = [row[1] for row in result]  # Column names are at index 1
            
            print(f"Current vocabulary columns: {columns}")
            
            # Add columns if they don't exist
            if 'ctx_ua' not in columns:
                await conn.execute(
                    text("ALTER TABLE vocabulary ADD COLUMN ctx_ua VARCHAR NULL")
                )
                print("✅ Added column ctx_ua to vocabulary table")
            else:
                print("ℹ️ Column ctx_ua already exists")
            
            if 'ctx_en' not in columns:
                await conn.execute(
                    text("ALTER TABLE vocabulary ADD COLUMN ctx_en VARCHAR NULL")
                )
                print("✅ Added column ctx_en to vocabulary table")
            else:
                print("ℹ️ Column ctx_en already exists")
            
            await conn.commit()
            print("\n✅ Migration completed successfully!")
            
        except Exception as e:
            print(f"❌ Error during migration: {e}")
            await conn.rollback()
            raise

if __name__ == "__main__":
    print("🚀 Running migration: add context translation columns to vocabulary...\n")
    asyncio.run(migrate())
