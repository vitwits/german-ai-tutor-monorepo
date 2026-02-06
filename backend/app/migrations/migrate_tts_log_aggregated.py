"""
Migration: Convert TTSLog from row-per-operation to aggregated statistics.

Old structure: Each TTS operation created a new row
New structure: Single aggregated row with cumulative counters per language/operation

This migration:
1. Backs up old tts_logs data if it exists
2. Drops the old tts_logs table
3. Creates new table with aggregated structure
4. Aggregates old data into single row (if data exists)
"""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import sys
import os

# Add parent directory to path to import models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.database import DATABASE_URL
from app.models import Base, TTSLog


async def migrate():
    """Run the migration"""
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        # 1. Backup old data if table exists (use raw SQL)
        try:
            result = await conn.execute(
                text("SELECT COUNT(*) FROM tts_logs")
            )
            row_count = result.scalar()
            print(f"\nFound {row_count} rows in old tts_logs table")
            
            if row_count > 0:
                # Create backup table
                await conn.execute(text("""
                    CREATE TABLE tts_logs_backup AS 
                    SELECT * FROM tts_logs
                """))
                print("✅ Backed up old tts_logs to tts_logs_backup")
        except Exception as e:
            print(f"Note: Old tts_logs table not found or already dropped: {e}")
        
        # 2. Drop old table
        try:
            await conn.execute(text("DROP TABLE IF EXISTS tts_logs"))
            print("✅ Dropped old tts_logs table")
        except Exception as e:
            print(f"Note: Could not drop tts_logs: {e}")
    
    # 3. Create new table from models
    async with engine.begin() as conn:
        # Create all tables (will create new tts_logs with aggregated schema)
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Created new tts_logs table with aggregated structure")
    
    # 4. Aggregate old data if backup exists
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        try:
            # Check if backup table exists
            result = await session.execute(
                text("SELECT COUNT(*) FROM tts_logs_backup")
            )
            backup_count = result.scalar()
            
            if backup_count > 0:
                print(f"\n🔄 Aggregating {backup_count} rows from backup...")
                
                # Aggregate data from old format to new format
                # Old format: language, chars, source (where source like '%cache%' or '%api%')
                aggregation_query = text("""
                    SELECT 
                        language,
                        CASE 
                            WHEN source LIKE '%cache%' THEN 'cache'
                            WHEN source LIKE '%api%' THEN 'api'
                            ELSE NULL
                        END as operation,
                        COUNT(*) as requests,
                        COALESCE(SUM(chars), 0) as total_chars
                    FROM tts_logs_backup
                    WHERE source LIKE '%vocabulary%'
                    GROUP BY language, operation
                """)
                
                result = await session.execute(aggregation_query)
                aggregated_data = result.all()
                
                if aggregated_data:
                    print(f"Aggregated data from backup:")
                    for lang, operation, requests, total_chars in aggregated_data:
                        print(f"  {lang} {operation}: {requests} requests, {total_chars} chars")
                    
                    # Create single aggregated row
                    agg_row = TTSLog()
                    
                    # Process aggregated data
                    for lang, operation, requests, total_chars in aggregated_data:
                        if lang and operation:
                            requests_field = f"{lang}_{operation}_requests"
                            chars_field = f"{lang}_{operation}_chars"
                            
                            setattr(agg_row, requests_field, requests)
                            setattr(agg_row, chars_field, total_chars)
                    
                    session.add(agg_row)
                    await session.commit()
                    print("✅ Created aggregated statistics row")
                else:
                    print("No vocabulary statistics found in backup, creating empty row")
                    agg_row = TTSLog()
                    session.add(agg_row)
                    await session.commit()
        except Exception as e:
            print(f"Note: Could not aggregate backup data: {e}")
            print("Creating empty aggregated row...")
            async with async_session() as session:
                agg_row = TTSLog()
                session.add(agg_row)
                await session.commit()
    
    await engine.dispose()
    print("\n✅ Migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(migrate())
