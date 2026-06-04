FROM python:3.11-slim

WORKDIR /app

# Встановлюємо системні залежності для аудіо (ffmpeg потрібен для твоїх скриптів)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Копіюємо файли Poetry та встановлюємо залежності
COPY pyproject.toml poetry.lock* ./
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-root

# Копіюємо решту коду програми
COPY . .

# Створюємо папки для БД та статики, якщо їх немає (будуть використовуватися для монтування томів)
RUN mkdir -p /app/data /app/static

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]