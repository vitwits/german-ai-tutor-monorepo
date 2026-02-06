#!/usr/bin/env python3
"""
Migration script to add 'page' column to ai_preferences table
Run this script after deploying the updated code:
    python migrate_add_page_to_ai_preferences.py
"""

import asyncio
import os
import sys
from sqlalchemy import inspect, text

# Add the app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from app.database import engine

async def run_migration():
    """Add page column to ai_preferences table if it doesn't exist"""
    
    async with engine.begin() as conn:
        # Check if column already exists
        def check_column_exists(connection):
            inspector = inspect(connection)
            columns = {col['name'] for col in inspector.get_columns('ai_preferences')}
            return 'page' in columns
        
        column_exists = await conn.run_sync(check_column_exists)
        
        if column_exists:
            print("✅ Column 'page' already exists in ai_preferences table")
            return
        
        # Add the column
        print("📝 Adding 'page' column to ai_preferences table...")
        await conn.execute(text("""
            ALTER TABLE ai_preferences 
            ADD COLUMN page VARCHAR NOT NULL DEFAULT 'texts'
        """))
        
        print("✅ Column 'page' added successfully!")
        print("\n📋 Updated schema:")
        print("  ├── id (INTEGER, PRIMARY KEY)")
        print("  ├── job (VARCHAR, UNIQUE, NOT NULL)")
        print("  ├── page (VARCHAR, NOT NULL) ← NEW")
        print("  ├── model_type (VARCHAR, NOT NULL)")
        print("  ├── lang (VARCHAR, NULL)")
        print("  ├── llm_model_id (INTEGER, FK, NULL)")
        print("  ├── tts_voice_id (INTEGER, FK, NULL)")
        print("  ├── created_at (DATETIME)")
        print("  └── updated_at (DATETIME)")

async def main():
    try:
        await run_migration()
        print("\n✨ Migration completed successfully!")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
