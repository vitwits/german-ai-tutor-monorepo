"""Add generation_cost_usd column to lessons table and drop texts table."""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def upgrade():
    """Add generation_cost_usd to lessons and drop texts table."""
    DATABASE_URL = "sqlite+aiosqlite:///./data/app.db"
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        print("📋 Checking lessons table...")
        # Check if generation_cost_usd column exists
        result = await conn.execute(text("PRAGMA table_info(lessons)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'generation_cost_usd' not in columns:
            await conn.execute(text("""
                ALTER TABLE lessons ADD COLUMN generation_cost_usd REAL DEFAULT 0.0
            """))
            print("✅ Added generation_cost_usd column to lessons table")
        else:
            print("ℹ️  Column generation_cost_usd already exists in lessons")
        
        print("📋 Checking texts table...")
        # Check if texts table exists and drop it
        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='texts'"))
        table_exists = result.fetchone()
        
        if table_exists:
            await conn.execute(text("PRAGMA foreign_keys=OFF"))
            await conn.execute(text("DROP TABLE IF EXISTS texts"))
            await conn.execute(text("PRAGMA foreign_keys=ON"))
            print("✅ Dropped legacy texts table")
        else:
            print("ℹ️  Table texts does not exist")
    
    await engine.dispose()
    print("🎉 Migration complete!")

if __name__ == "__main__":
    asyncio.run(upgrade())
