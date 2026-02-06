"""
Migration: Add UserBilling table for energy-based billing system
Purpose: Track user energy, subscription status, and billing periods
Date: 2026-02-03
"""

import sqlite3
import os
from datetime import datetime


def migrate():
    """Create user_billing table"""
    
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/app.db"))
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Create user_billing table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_billing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL UNIQUE,
                subscription_status TEXT DEFAULT 'active',
                billing_start_day INTEGER NOT NULL,
                billing_end_day INTEGER,
                energy_left REAL DEFAULT 0.0,
                daily_spending REAL DEFAULT 0.0,
                price_per_point_usd REAL DEFAULT 0.0,
                last_energy_reset DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_billing_reset DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        
        conn.commit()
        print("✅ user_billing table created successfully")
        
    except sqlite3.OperationalError as e:
        if "already exists" in str(e):
            print(f"⚠️  user_billing table already exists")
        else:
            print(f"❌ Error creating user_billing table: {e}")
            conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
