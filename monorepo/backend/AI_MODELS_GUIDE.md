# AI Models Management - Implementation Guide

## ✅ Что было создано:

### 1. **Database Model** (`app/models.py`)
Новая таблица `AIResource` с полями:
- `id` - автогенерируемый первичный ключ
- `name` - дружелюбное имя (напр., "Gemini 2.5 Flash Lite")
- `model_id` - идентификатор для кода (напр., "gemini-2.5-flash-lite")
- `input_type` - типи вхідних даних (text|audio|image|text,audio|...)
- `output_type` - тип вихідних даних (text|audio|image)
- `price_per_unit` - ціна за 1млн токенів/символів
- `unit_type` - одиниця виміру (per_1m_tokens|per_character)
- `provider` - провайдер (google|azure|openai|...)
- `is_active` - активна модель чи ні
- `created_at`, `updated_at` - часові мітки

### 2. **Admin Panel Page** (`admin_router.py`)
Нова вкладка `/admin/ai-models` з функціоналом:
- ✅ Перегляд всіх доданих моделей у таблиці
- ✅ Додавання нових моделей через модальне вікно
- ✅ Редагування існуючих моделей (функціонал готовий, кнопка 'Edit')
- ✅ Видалення моделей з підтвердженням

### 3. **API Endpoints** (`admin_router.py`)
- `POST /admin/api/ai-models` - створення нової моделі
- `PUT /admin/api/ai-models/{id}` - оновлення моделі
- `DELETE /admin/api/ai-models/{id}` - видалення моделі

### 4. **Migration Script** (`migrate_add_ai_resources.py`)
Скрипт для створення таблиці в БД

## 🚀 Як запустити:

### Крок 1: Створити таблицю в БД
```bash
cd /Users/omicron/Desktop/german_ai_tutor/monorepo/backend
python migrate_add_ai_resources.py
```

### Крок 2: Перезагрузити бекенд
```bash
# Перезавантажте FastAPI сервер (якщо він запущений)
# Сервер автоматично завантажить нову модель
```

### Крок 3: Доступ до адмін-панелі
1. Перейдіть на `http://localhost:8000/admin/ai-models`
2. Авторизуйтесь як адмін
3. Почніть додавати моделі!

## 📝 Приклади моделей для додавання:

### Gemini моделі:
```
Name: Gemini 2.5 Flash Lite (Input)
Model ID: gemini-2.5-flash-lite-input
Input Type: text
Output Type: text
Price: 0.1
Unit Type: per_1m_tokens
Provider: google
```

```
Name: Gemini 2.5 Flash Lite (Output)
Model ID: gemini-2.5-flash-lite-output
Input Type: text
Output Type: text
Price: 0.4
Unit Type: per_1m_tokens
Provider: google
```

### Google TTS моделі:
```
Name: Google TTS Chirp3
Model ID: google-tts-chirp3
Input Type: text
Output Type: audio
Price: 0.00003
Unit Type: per_character
Provider: google
```

```
Name: Google TTS Neural2
Model ID: google-tts-neural2
Input Type: text
Output Type: audio
Price: 0.000016
Unit Type: per_character
Provider: google
```

## 🔧 Функціонал готовий до розширення:

### Що можна розробити далі:
1. Зберігання голосів озвучки (окрема таблиця `tts_voices`)
2. Зв'язок голосів з моделями
3. Логування витрат по моделям
4. Аналітика по використанню ресурсів
5. Автоматичне обчислення цін на основі цін з таблиці

## 📌 Примітки:

- `Model ID` повинен бути унікальним (система не дозволить дублікати)
- Всі поля обов'язкові, крім ID (генерується автоматично)
- Можна редагувати будь-яке поле після створення
- Неактивні моделі залишаються в БД, але можуть бути пропущені при розрахунку

---

Готово! 🎉 Тепер можеш додавати нові моделі прямо з адмін-панелі!
