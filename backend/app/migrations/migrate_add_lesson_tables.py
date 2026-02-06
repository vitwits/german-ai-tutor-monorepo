"""
Migration: Add Lesson, UserLesson, and LessonAudio tables
Purpose: Support global lessons with per-user references for eventual shared library
Date: 2025-01-17
"""

import sqlite3
import os
from pathlib import Path

def migrate():
    """Create three new tables for global lesson storage"""
    
    # From migrations folder: app/migrations/... -> ../../data/app.db
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/app.db"))
    
    # Ensure path exists
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Create lessons table (global lessons, anonymous)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id TEXT PRIMARY KEY,
                title TEXT,
                level TEXT,
                content_json TEXT,
                quiz_json TEXT,
                audio_status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create user_lessons table (junction table for user access)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                lesson_id TEXT NOT NULL,
                is_favorite INTEGER DEFAULT 0,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (lesson_id) REFERENCES lessons(id),
                UNIQUE(user_id, lesson_id)
            )
        """)
        
        # Create lesson_audio table (audio metadata per sentence)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lesson_audio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_id TEXT NOT NULL,
                sentence_index INTEGER NOT NULL,
                lang TEXT DEFAULT 'de',
                audio_path TEXT,
                status TEXT DEFAULT 'pending',
                generated_at DATETIME,
                FOREIGN KEY (lesson_id) REFERENCES lessons(id),
                UNIQUE(lesson_id, sentence_index, lang)
            )
        """)
        
        # Add lesson_id column to quiz_results (nullable, for backward compatibility)
        try:
            cursor.execute("""
                PRAGMA table_info(quiz_results)
            """)
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'lesson_id' not in columns:
                cursor.execute("""
                    ALTER TABLE quiz_results
                    ADD COLUMN lesson_id TEXT REFERENCES lessons(id)
                """)
                print("   - Added lesson_id column to quiz_results")
        except sqlite3.OperationalError:
            # Table doesn't exist yet, that's OK
            print("   - quiz_results table not created yet (will be created by alembic/create_all)")
        
        conn.commit()
        print("✅ Migration completed successfully")
        print("   - Created lessons table")
        print("   - Created user_lessons table")
        print("   - Created lesson_audio table")
        print("   - Added lesson_id column to quiz_results")
        
    except sqlite3.OperationalError as e:
        if "already exists" in str(e):
            print("✅ Tables already exist, skipping creation")
        else:
            print(f"❌ Migration failed: {e}")
            conn.rollback()
            raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
