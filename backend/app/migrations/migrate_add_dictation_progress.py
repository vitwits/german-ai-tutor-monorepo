"""
Migration: add dictation_progress table for persistent dictation state.
"""

import asyncio
import sqlite3
from pathlib import Path


def _resolve_sqlite_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "app.db"


async def migrate():
    db_path = _resolve_sqlite_path()
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dictation_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            lesson_id TEXT NOT NULL,
            order_json TEXT,
            passed_indices_json TEXT,
            cursor INTEGER DEFAULT 0,
            playback_rate REAL DEFAULT 0.8,
            completed_once INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, lesson_id)
        )
        """
    )

    conn.commit()
    conn.close()
    print("✅ dictation_progress table ensured")


if __name__ == "__main__":
    asyncio.run(migrate())
