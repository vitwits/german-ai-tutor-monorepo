"""
Migration: Remove deprecated credits column from users table
Date: 2026-02-09
Reason: Migrated to UserBilling system with energy_left instead of credits
"""
import asyncio
import os
import sqlite3
from pathlib import Path

async def migrate_drop_credits():
    """Remove the credits column from users table"""
    # Get the correct database path - it's in monorepo/backend/data/app.db
    db_path = "/Users/omicron/Desktop/german_ai_tutor/backend/data/app.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return
    
    print(f"✅ Database found at {db_path}")
    
    # Use synchronous sqlite3 for this migration (simpler for table recreation)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check if the credits column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if "credits" not in column_names:
            print("ℹ️ Credits column not found in users table - already removed or doesn't exist")
            return
        
        print("Removing credits column from users table...")
        
        # SQLite doesn't support ALTER TABLE DROP COLUMN directly
        # We need to recreate the table without the credits column
        cursor.execute("PRAGMA foreign_keys=OFF")
        
        # Create new table without credits column
        cursor.execute("""
            CREATE TABLE users_new (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                interface_language TEXT DEFAULT 'ukr',
                level TEXT DEFAULT 'A2',
                is_admin INTEGER DEFAULT 0,
                llm_cost REAL DEFAULT 0.0,
                tts_cost REAL DEFAULT 0.0,
                total_cost REAL DEFAULT 0.0,
                library_view_mode TEXT DEFAULT 'list',
                library_per_page INTEGER DEFAULT 20,
                vocab_view_mode TEXT DEFAULT 'list',
                vocab_per_page INTEGER DEFAULT 20,
                vocab_session_size INTEGER DEFAULT 20,
                study_batch_size INTEGER DEFAULT 20
            )
        """)
        
        # Copy data from old table to new table (excluding credits)
        cursor.execute("""
            INSERT INTO users_new (
                id, email, password_hash, interface_language, level, is_admin,
                llm_cost, tts_cost, total_cost,
                library_view_mode, library_per_page, vocab_view_mode, vocab_per_page,
                vocab_session_size, study_batch_size
            )
            SELECT 
                id, email, password_hash, interface_language, level, is_admin,
                llm_cost, tts_cost, total_cost,
                library_view_mode, library_per_page, vocab_view_mode, vocab_per_page,
                vocab_session_size, study_batch_size
            FROM users
        """)
        
        # Drop old table and rename new one
        cursor.execute("DROP TABLE users")
        cursor.execute("ALTER TABLE users_new RENAME TO users")
        
        # Re-enable foreign keys
        cursor.execute("PRAGMA foreign_keys=ON")
        
        conn.commit()
        print("✅ Migration completed: credits column removed from users table")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error during migration: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    asyncio.run(migrate_drop_credits())
