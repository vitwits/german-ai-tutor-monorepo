"""Drop legacy texts table."""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def upgrade():
    """Drop texts table (legacy)."""
    DATABASE_URL = "sqlite+aiosqlite:///./app.db"
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        # Check if table exists
        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='texts'"))
        table_exists = await result.fetchone()
        
        if table_exists:
            # First drop foreign key constraints if any
            await conn.execute(text("PRAGMA foreign_keys=OFF"))
            await conn.execute(text("DROP TABLE IF EXISTS texts"))
            await conn.execute(text("PRAGMA foreign_keys=ON"))
            print("✅ Dropped legacy texts table")
        else:
            print("ℹ️  Table texts does not exist")
    
    await engine.dispose()

async def downgrade():
    """Recreate texts table (not recommended)."""
    print("⚠️  Downgrade not supported - texts table was legacy and shouldn't be restored")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "down":
        asyncio.run(downgrade())
    else:
        asyncio.run(upgrade())
