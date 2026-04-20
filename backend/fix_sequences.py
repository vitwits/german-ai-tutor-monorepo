#!/usr/bin/env python3
"""
Виправлення послідовностей (sequences) в PostgreSQL після міграції
"""

import asyncio
import sys
import os
from pathlib import Path

from dotenv import load_dotenv
env_path = Path('/Users/omicron/Desktop/german_ai_tutor/.env')
load_dotenv(env_path)

sys.path.insert(0, '/Users/omicron/Desktop/german_ai_tutor/backend')

async def fix_sequences():
    """Виправляє всі послідовності в PostgreSQL"""
    
    import asyncpg
    
    print("🔧 Виправляємо послідовності в PostgreSQL...\n")
    
    conn = await asyncpg.connect(
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        database=os.getenv('POSTGRES_DB'),
        host=os.getenv('POSTGRES_HOST'),
        port=int(os.getenv('POSTGRES_PORT')),
    )
    
    try:
        # Список таблиць з auto-increment ID
        tables_with_sequences = [
            ('billing_plans', 'id'),
            ('llm_models', 'id'),
            ('tts_models', 'id'),
            ('llm_prices', 'id'),
            ('tts_voices', 'id'),
            ('ai_preferences', 'id'),
            ('model_prompts', 'id'),
            ('lesson_audio', 'id'),
            ('sentences', 'id'),
            ('user_lessons', 'id'),
            ('user_favorite_sentences', 'id'),
            ('quiz_results', 'id'),
            ('user_blocked_sentences', 'id'),
            ('user_billing', 'id'),
            ('tts_logs', 'id'),
            ('temp_sentences', 'id'),
            ('sentence_batches', 'id'),
            ('reported_lessons', 'id'),
        ]
        
        for table_name, col_name in tables_with_sequences:
            try:
                # Отримуємо максимальне значення ID
                max_id_result = await conn.fetchval(f"SELECT MAX({col_name}) FROM {table_name}")
                max_id = max_id_result or 0
                
                # Встановлюємо послідовність на max_id + 1
                new_sequence_value = max_id + 1
                sequence_name = f"{table_name}_{col_name}_seq"
                
                await conn.execute(f"ALTER SEQUENCE {sequence_name} RESTART WITH {new_sequence_value}")
                
                print(f"✅ {table_name}: послідовність встановлена на {new_sequence_value} (max_id={max_id})")
            
            except Exception as e:
                print(f"⚠️  {table_name}: {e}")
                continue
        
        print("\n✨ Послідовності виправлені!")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(fix_sequences())
