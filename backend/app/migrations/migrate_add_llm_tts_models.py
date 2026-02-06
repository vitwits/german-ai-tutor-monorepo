#!/usr/bin/env python3
"""
Migration script to add llm_models and tts_models tables to the database
Run this script after deploying the updated code:
    python migrate_add_llm_tts_models.py
"""

import asyncio
import os
import sys
from sqlalchemy import inspect

# Add the app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.database import engine, Base
from app.models import LLMModel, TTSModel

async def run_migration():
    """Create the llm_models and tts_models tables if they don't exist"""
    
    async with engine.begin() as conn:
        # Check if tables already exist using run_sync
        def check_tables_exist(connection):
            inspector = inspect(connection)
            table_names = inspector.get_table_names()
            return {
                'llm_models': 'llm_models' in table_names,
                'tts_models': 'tts_models' in table_names
            }
        
        tables_status = await conn.run_sync(check_tables_exist)
        
        if tables_status['llm_models'] and tables_status['tts_models']:
            print("✅ Tables 'llm_models' and 'tts_models' already exist")
            return
        
        # Create the tables
        print("📝 Creating 'llm_models' and 'tts_models' tables...")
        await conn.run_sync(Base.metadata.create_all)
        
        if not tables_status['llm_models']:
            print("✅ Table 'llm_models' created successfully!")
        if not tables_status['tts_models']:
            print("✅ Table 'tts_models' created successfully!")
        
        print("\n📌 Hint: You can now manage LLM and TTS models through the admin panel")

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
