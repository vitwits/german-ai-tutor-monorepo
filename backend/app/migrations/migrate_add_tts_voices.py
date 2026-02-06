"""
Migration: Create tts_voices table

This migration creates the tts_voices table with the following columns:
- id (primary key)
- voice_name (string, not null)
- tts_model_id (foreign key to tts_models)
- lang (string: EN|DE|UA, not null)
- gender (string: male|female, not null)
- is_active (boolean, default True)
- created_at (datetime)
- updated_at (datetime)

Usage:
    python migrate_add_tts_voices.py
"""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Add the app directory to the path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir.parent))

from app.database import DATABASE_URL


async def migrate():
    """Create tts_voices table"""
    engine = create_async_engine(DATABASE_URL)
    
    async with engine.begin() as conn:
        try:
            print("Creating tts_voices table...")
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS tts_voices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    voice_name VARCHAR(255) NOT NULL,
                    tts_model_id INTEGER NOT NULL,
                    lang VARCHAR(10) NOT NULL,
                    gender VARCHAR(20) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tts_model_id) REFERENCES tts_models(id)
                )
            """))
            print("✅ Successfully created tts_voices table")
                
        except Exception as e:
            print(f"❌ Error during migration: {e}")
            raise
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
