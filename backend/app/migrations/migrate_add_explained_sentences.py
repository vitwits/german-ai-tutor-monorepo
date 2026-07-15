"""
Migration: add explained_sentences table
Run: python -m app.migrations.migrate_add_explained_sentences
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy import text
from app.database import engine


async def migrate():
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS explained_sentences (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL REFERENCES users(id),
                text_id VARCHAR NOT NULL,
                sentence_index INTEGER NOT NULL,
                sentence_text TEXT NOT NULL,
                explanation_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_explained_sentences_user_text
            ON explained_sentences(user_id, text_id, sentence_index)
        """))
    print("✅ Migration complete: explained_sentences table created.")


if __name__ == "__main__":
    asyncio.run(migrate())
