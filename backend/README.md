
pip install poetry
poetry install --no-root

# Якщо через poetry
poetry run uvicorn app.main:app --reload --port 8000

# Якщо через звичайний pip/venv
uvicorn app.main:app --reload --port 8000

# Документація (Swagger) доступна тут: 
http://localhost:8000/docs


# Просто виконай poetry lock (без прапорців) — це оновить lock-файл з твоєю новою версією bcrypt
poetry lock

# Потім встанови залежності:
poetry install --no-root

# Перевір версію Poetry (щоб підтвердити):
poetry --version