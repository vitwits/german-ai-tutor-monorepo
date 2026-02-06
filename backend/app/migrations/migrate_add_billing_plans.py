"""
Migration: Add BillingPlan table for billing configuration
Purpose: Store billing plans with monthly credits, cap days, and daily energy
Date: 2026-02-03
"""

import sqlite3
import os
from pathlib import Path


def migrate():
    """Create billing_plans table"""
    
    # From migrations folder: app/migrations/... -> ../../data/app.db
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/app.db"))
    
    # Ensure path exists
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Create billing_plans table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                monthly_credit REAL NOT NULL,
                max_cap_days INTEGER NOT NULL,
                day_energy REAL NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        print("✅ billing_plans table created successfully")
        
    except sqlite3.OperationalError as e:
        if "already exists" in str(e):
            print(f"⚠️  billing_plans table already exists")
        else:
            print(f"❌ Error creating billing_plans table: {e}")
            conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
