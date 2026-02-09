"""
Migration: Add created_at timestamp to vocabulary table
Date: 2026-02-09
Reason: Track when words were added to sort them by creation date
"""
import sqlite3
from datetime import datetime

def migrate_add_created_at():
    """Add created_at column to vocabulary table"""
    db_path = "/Users/omicron/Desktop/german_ai_tutor/backend/data/app.db"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(vocabulary)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if "created_at" in column_names:
            print("ℹ️ created_at column already exists in vocabulary table")
            return
        
        print("Adding created_at column to vocabulary table...")
        
        # Add the column without DEFAULT (SQLite limitation)
        cursor.execute("""
            ALTER TABLE vocabulary
            ADD COLUMN created_at TIMESTAMP
        """)
        
        # Set existing rows to current timestamp
        now = datetime.now().isoformat()
        cursor.execute(f"""
            UPDATE vocabulary SET created_at = ? WHERE created_at IS NULL
        """, (now,))
        
        conn.commit()
        print("✅ Migration completed: created_at column added to vocabulary table")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error during migration: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_add_created_at()
