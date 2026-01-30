#!/usr/bin/env python3
"""
Migration script to add gender column to ai_preferences table
and populate it based on the associated tts_voice gender

Run this script after deploying the updated code:
    python migrate_add_gender_to_ai_preferences.py
"""

import asyncio
import os
import sys
from sqlalchemy import inspect, Column, String, text

# Add the app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from app.database import engine

async def run_migration():
    """Add gender column to ai_preferences and populate it"""
    
    # Step 1: Check if column exists
    async with engine.begin() as conn:
        def check_column_exists(connection):
            inspector = inspect(connection)
            columns = [col['name'] for col in inspector.get_columns('ai_preferences')]
            return 'gender' in columns
        
        column_exists = await conn.run_sync(check_column_exists)
        
        if column_exists:
            print("✅ Column 'gender' already exists in ai_preferences")
            return
        
        # Add the gender column
        print("📝 Adding 'gender' column to ai_preferences...")
        await conn.execute(text(
            "ALTER TABLE ai_preferences ADD COLUMN gender VARCHAR NULL"
        ))
        print("✅ Column 'gender' added successfully!")
    
    # Step 2: Populate gender based on tts_voice relationship (separate transaction)
    async with engine.begin() as conn:
        print("\n📝 Populating gender values from tts_voices...")
        
        # For TTS jobs, get the gender from the associated tts_voice
        update_query = text("""
            UPDATE ai_preferences
            SET gender = (
                SELECT tv.gender
                FROM tts_voices tv
                WHERE tv.id = ai_preferences.tts_voice_id
            )
            WHERE model_type = 'tts' AND tts_voice_id IS NOT NULL
        """)
        
        result = await conn.execute(update_query)
        print(f"✅ Updated {result.rowcount} records with gender values!")
    
    # Step 3: Print summary (separate transaction)
    async with engine.begin() as conn:
        print("\n📋 Gender summary:")
        summary_query = text("""
            SELECT job, gender, voice_name FROM ai_preferences
            LEFT JOIN tts_voices ON ai_preferences.tts_voice_id = tts_voices.id
            WHERE model_type = 'tts'
            ORDER BY job
        """)
        
        result = await conn.execute(summary_query)
        for row in result:
            job, gender, voice = row
            print(f"   - {job}: {gender} ({voice})")
        
        print("\n✅ Migration completed successfully!")

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🚀 MIGRATION: Add gender column to ai_preferences")
    print("=" * 70 + "\n")
    
    try:
        asyncio.run(run_migration())
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n" + "=" * 70)
    print("✅ All done!")
    print("=" * 70 + "\n")
