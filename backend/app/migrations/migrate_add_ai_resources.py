#!/usr/bin/env python3
"""
Migration script to add ai_resources table to the database
Run this script after deploying the updated code:
    python migrate_add_ai_resources.py
"""

import asyncio
import os
import sys
from sqlalchemy import inspect

# Add the app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.database import engine, Base
from app.models import AIResource

async def run_migration():
    """Create the ai_resources table if it doesn't exist"""
    
    async with engine.begin() as conn:
        # Check if table already exists using run_sync
        def check_table_exists(connection):
            inspector = inspect(connection)
            return 'ai_resources' in inspector.get_table_names()
        
        table_exists = await conn.run_sync(check_table_exists)
        
        if table_exists:
            print("✅ Table 'ai_resources' already exists")
            return
        
        # Create the table
        print("📝 Creating 'ai_resources' table...")
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Table 'ai_resources' created successfully!")
        
        # Optional: Insert initial data
        print("\n📌 Hint: You can now add AI models through the admin panel at /admin/ai-models")

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
