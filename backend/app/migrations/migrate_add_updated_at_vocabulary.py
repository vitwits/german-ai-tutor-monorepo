"""
Migration: Add updated_at timestamp to vocabulary table
Date: 2026-02-09
Reason: Track when words were last edited
"""
import sqlite3
from datetime import datetime

def migrate_add_updated_at():
    """Add updated_at column to vocabulary table"""
    db_path = "/Users/omicron/Desktop/german_ai_tutor/backend/data/app.db"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(vocabulary)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if "updated_at" in column_names:
            print("ℹ️ updated_at column already exists in vocabulary table")
            return
        
        print("Adding updated_at column to vocabulary table...")
        
        # Add the column
        cursor.execute("""
            ALTER TABLE vocabulary
            ADD COLUMN updated_at TIMESTAMP
        """)
        
        # Set updated_at to created_at for existing rows
        cursor.execute("""
            UPDATE vocabulary SET updated_at = created_at WHERE updated_at IS NULL
        """)
        
        conn.commit()
        print("✅ Migration completed: updated_at column added to vocabulary table")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error during migration: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_add_updated_at()
