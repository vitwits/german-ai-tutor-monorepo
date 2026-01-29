#!/usr/bin/env python3
"""
Migration script to add ai_preferences table to the database
Run this script after deploying the updated code:
    python migrate_add_ai_preferences.py
"""

import asyncio
import os
import sys
from sqlalchemy import inspect

# Add the app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from app.database import engine, Base
from app.models import AIPreference

async def run_migration():
    """Create the ai_preferences table if it doesn't exist"""
    
    async with engine.begin() as conn:
        # Check if table already exists using run_sync
        def check_table_exists(connection):
            inspector = inspect(connection)
            return 'ai_preferences' in inspector.get_table_names()
        
        table_exists = await conn.run_sync(check_table_exists)
        
        if table_exists:
            print("✅ Table 'ai_preferences' already exists")
            return
        
        # Create the table
        print("📝 Creating 'ai_preferences' table...")
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Table 'ai_preferences' created successfully!")
        
        # Print table schema
        print("\n📋 Table schema:")
        print("  ├── id (INTEGER, PRIMARY KEY)")
        print("  ├── job (VARCHAR, UNIQUE, NOT NULL)")
        print("  ├── model_type (VARCHAR, NOT NULL)")
        print("  ├── lang (VARCHAR, NULL)")
        print("  ├── llm_model_id (INTEGER, FK → llm_models.id, NULL)")
        print("  ├── tts_voice_id (INTEGER, FK → tts_voices.id, NULL)")
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
