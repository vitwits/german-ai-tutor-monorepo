"""
Migration: Add explained_words table
Date: 2026-07-12
Reason: Persist word explanations bound to exact word positions in lesson text
"""

import sqlite3
from pathlib import Path


def migrate_add_explained_words_table():
    backend_dir = Path(__file__).resolve().parents[2]
    db_path = backend_dir / "data" / "app.db"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS explained_words (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                text_id TEXT NOT NULL,
                origin TEXT NOT NULL,
                sentence_index INTEGER NOT NULL,
                start_index INTEGER NOT NULL,
                end_index INTEGER NOT NULL,
                explanation_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_explained_words_user_text
            ON explained_words(user_id, text_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_explained_words_position
            ON explained_words(user_id, text_id, sentence_index, start_index, end_index)
            """
        )

        conn.commit()
        print("✅ Migration completed: explained_words table is ready")
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_add_explained_words_table()
