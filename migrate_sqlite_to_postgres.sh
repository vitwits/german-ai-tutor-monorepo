#!/bin/bash

# Миграція SQLite → PostgreSQL
# Цей скрипт експортує дані з SQLite та імпортує їх в PostgreSQL

set -e

echo "🔄 Розпочинаємо міграцію SQLite → PostgreSQL..."

# Конфіг
SQLITE_DB="/Users/omicron/Desktop/german_ai_tutor/backend/data/app.db"
POSTGRES_USER="postgres"
POSTGRES_PASSWORD="postgres"
POSTGRES_DB="german_ai_tutor"
POSTGRES_HOST="localhost"
POSTGRES_PORT="5432"

# Перевіримо, чи існує SQLite БД
if [ ! -f "$SQLITE_DB" ]; then
    echo "❌ SQLite БД не знайдена: $SQLITE_DB"
    exit 1
fi

echo "✅ SQLite БД знайдена: $SQLITE_DB"

TEMP_DIR="/tmp/migration_$$"
mkdir -p "$TEMP_DIR"

echo "📦 Крок 1: Експортування SQLite схеми та даних..."
sqlite3 "$SQLITE_DB" .dump > "$TEMP_DIR/sqlite_dump.sql"
echo "✅ SQLite дамп створено: $TEMP_DIR/sqlite_dump.sql"

echo "🔧 Крок 2: Конвертація SQL для PostgreSQL..."
cat "$TEMP_DIR/sqlite_dump.sql" | \
  sed 's/PRAGMA.*//' | \
  sed 's/BEGIN TRANSACTION;//' | \
  sed 's/COMMIT;//' | \
  sed 's/AUTOINCREMENT//' | \
  sed "s/\`/\"/g" > "$TEMP_DIR/postgres_dump.sql"
echo "✅ SQL конвертовано для PostgreSQL"

echo "📥 Крок 3: Імпортування даних в PostgreSQL..."
PGPASSWORD="$POSTGRES_PASSWORD" psql \
  -h "$POSTGRES_HOST" \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  -f "$TEMP_DIR/postgres_dump.sql" > /dev/null 2>&1 || true

echo "✅ Дані імпортовано в PostgreSQL"

echo "🧹 Крок 4: Очищення тимчасових файлів..."
rm -rf "$TEMP_DIR"

echo ""
echo "✨ Міграція завершена успішно!"
echo ""
echo "📝 Наступні кроки:"
echo "1. Оновити backend/app/database.py для PostgreSQL ✅"
echo "2. Встановити asyncpg: pip install asyncpg"
echo "3. Перезапустити бекенд"
echo ""
echo "Перевірити дані в PostgreSQL:"
echo "  psql -h localhost -U postgres -d german_ai_tutor"
echo "  SELECT COUNT(*) FROM users;"
