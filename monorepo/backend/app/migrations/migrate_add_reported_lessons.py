"""
Migration: Add ReportedLesson table for tracking reported texts
Purpose: Support user reporting of problematic lessons with admin management
Date: 2026-02-03
"""

import sqlite3
import os
from pathlib import Path


def migrate():
    """Create reported_lessons table"""
    
    # From migrations folder: app/migrations/... -> ../../data/app.db
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/app.db"))
    
    # Ensure path exists
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Create reported_lessons table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reported_lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_id VARCHAR NOT NULL,
                user_id VARCHAR NOT NULL,
                status VARCHAR DEFAULT 'reported',
                admin_notes TEXT,
                reported_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                reviewed_at DATETIME,
                FOREIGN KEY (lesson_id) REFERENCES lessons(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        conn.commit()
        print("✅ Created reported_lessons table")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
