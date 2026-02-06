#!/usr/bin/env python3
"""
Міграція: видалення таблиці ai_resources та створення таблиці llm_prices
"""
import asyncio
from sqlalchemy import text
from app.database import engine


async def main():
    async with engine.begin() as conn:
        try:
            # Перевіримо чи таблиця ai_resources існує
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_resources'")
            )
            ai_resources_exists = result.fetchone() is not None
            
            if ai_resources_exists:
                await conn.execute(text("DROP TABLE ai_resources"))
                print("✅ Таблиця 'ai_resources' видалена")
            else:
                print("ℹ️  Таблиця 'ai_resources' не існує")
            
            # Перевіримо чи таблиця llm_prices вже існує
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='llm_prices'")
            )
            llm_prices_exists = result.fetchone() is not None
            
            if llm_prices_exists:
                print("ℹ️  Таблиця 'llm_prices' вже існує")
            else:
                # Створюємо таблицю llm_prices
                await conn.execute(text("""
                    CREATE TABLE llm_prices (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        human_name VARCHAR NOT NULL,
                        llm_model_id INTEGER NOT NULL,
                        direction VARCHAR NOT NULL,
                        data_type VARCHAR NOT NULL,
                        lang VARCHAR,
                        price_per_unit FLOAT NOT NULL,
                        is_active BOOLEAN DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (llm_model_id) REFERENCES llm_models(id)
                    )
                """))
                print("✅ Таблиця 'llm_prices' створена")
            
            await conn.commit()
            print("✅ Міграція успішно завершена")
            
        except Exception as e:
            print(f"❌ Помилка: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
