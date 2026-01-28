"""
Міграція: Додати study_batch_size колонку до users таблиці.
"""

import sqlite3

def migrate():
    db_path = "./app/data.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get table info
        cursor.execute("PRAGMA table_info(users)")
        columns = {row[1] for row in cursor.fetchall()}
        
        if 'study_batch_size' in columns:
            print("✅ Column 'study_batch_size' already exists")
        else:
            # Add column with default value 50
            cursor.execute("ALTER TABLE users ADD COLUMN study_batch_size INTEGER DEFAULT 50")
            conn.commit()
            print("✅ Column 'study_batch_size' added successfully")
        
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    migrate()
