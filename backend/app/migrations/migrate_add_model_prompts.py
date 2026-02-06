"""
Міграція: Додати нову таблицю model_prompts з колонкою page для прив'язки до вкладок.
"""

import sqlite3

def migrate():
    db_path = "./data/app.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='model_prompts'")
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            # Check if page column exists
            cursor.execute("PRAGMA table_info(model_prompts)")
            columns = {row[1] for row in cursor.fetchall()}
            
            if 'page' in columns:
                print("✅ Table 'model_prompts' already has 'page' column")
            else:
                # Add page column
                cursor.execute("ALTER TABLE model_prompts ADD COLUMN page TEXT NOT NULL DEFAULT 'texts'")
                conn.commit()
                print("✅ Column 'page' added to 'model_prompts'")
        else:
            # Create table
            cursor.execute("""
            CREATE TABLE model_prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                page TEXT NOT NULL,
                prompt TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.commit()
            print("✅ Table 'model_prompts' created successfully")
        
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    migrate()
