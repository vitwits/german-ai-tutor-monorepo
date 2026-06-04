import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Завантажимо .env файл
# У Docker змінні середовища будуть передані напряму, для локальної розробки load_dotenv() знайде .env у корені
load_dotenv()

# Визначення бази даних - використовуємо PostgreSQL або SQLite залежно від конфігу
DB_TYPE = os.getenv("DB_TYPE", "sqlite")  # 'sqlite' або 'postgres'

if DB_TYPE == "postgres":
    # PostgreSQL конфіг
    POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "german_ai_tutor")
    DATABASE_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
else:
    # SQLite конфіг (за замовчуванням)
    DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/app.db"))
    DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

print(f"🔌 Використовуємо базу даних: {DB_TYPE.upper()}")
print(f"📍 Connection String: {DATABASE_URL.split('@')[0] if '@' in DATABASE_URL else DATABASE_URL[:50]}...")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
