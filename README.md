Ось більш чистий, структурований і зручний для читання Markdown-варіант твоєї інструкції:

```markdown
# Як запустити Flask-додаток локально на macOS

## 1. Перевір версію Python

Потрібен **Python 3.9 – 3.12**

```bash
python3 --version
```

- Якщо бачиш 3.9+ (наприклад, 3.10.14, 3.11, 3.12) → все гаразд  
- Якщо Python відсутній або стара версія → встанови:

Через Homebrew (рекомендовано):
```bash
brew install python@3.12
```

Або завантаж з [python.org](https://www.python.org/downloads/)

---

## 2. Створи та активуй віртуальне середовище

```bash
# 1. Перейди в папку проєкту
cd шлях/до/твого/проєкту

# 2. Створи venv
python3 -m venv venv

# 3. Активуй (macOS / Linux)
source venv/bin/activate
```

Після активації в терміналі з’явиться `(venv)` перед промптом.

---

## 3. Встанови залежності

```bash
# Онови pip та базові інструменти
pip install --upgrade pip setuptools wheel

# Основні пакети
pip install flask flask-login flask-bcrypt python-dotenv flask-admin flask-sqlalchemy flask-cors

# Google пакети
pip install google-genai
pip install google-cloud-texttospeech
pip install azure-cognitiveservices-speech
```

### Окремо для Apple Silicon (M1/M2/M3/M4), якщо виникають проблеми з `google-cloud-texttospeech`:

```bash
# Варіант 1 — примусово скомпілювати grpcio
pip install --no-binary :all: grpcio
pip install google-cloud-texttospeech --no-cache-dir

# Варіант 2 — часто працює краще
pip install --prefer-binary google-cloud-texttospeech
```

---

## 4. Налаштуй API ключі (обов’язково!)

Створи файл `.env` у корені проєкту:

```env
# .env
GOOGLE_API_KEY=твій_ключ_для_gemini_generative_ai

# Якщо використовується Text-to-Speech (зазвичай потрібно)
GOOGLE_APPLICATION_CREDENTIALS=/шлях/до/твого/service-account.json

# Azure Speech (для української озвучки)
AZURE_SPEECH_KEY=EmA4Xsh4MX9eB17KvNogLfeyGK0kZDL6pfux5FkqqzK6r8QCSamuJQQJ99CAACPV0roXJ3w3AAAYACOGRyja
AZURE_SPEECH_REGION=germanywestcentral
```

- **Gemini** → достатньо лише `GOOGLE_API_KEY`  
- **Cloud Text-to-Speech** → потрібен service account JSON-файл (створюється в Google Cloud Console → IAM & Admin → Service Accounts)


```markdown
# SECRET_KEY у Flask — коротко

**Що це?**  
Секретний ключ для підпису сесій, CSRF-токенів, remember-me тощо. Без нього або зі слабким ключем — вразливість.

**Де задавати?**  
У `.env` (ніколи не коміть у git!):

```env
SECRET_KEY=твій_дуже_довгий_випадковий_рядок
```

**Як згенерувати (рекомендовано 2025+):**

```bash
# Найкращий варіант — 48+ символів
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Приклад (ніколи не використовуй цей!):
```
SECRET_KEY=K9UgLopISOwraERUgIbaS6J2VLbxph9mu5U68jK-gJJ4zw7xg1xGxfXD4StBCRG4
```

**Альтернатива (hex):**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

**Головне правило:**  
≥32 байти випадкових даних · унікальний для проєкту · не "super-secret-key"
```
---

## 5. Запуск додатку

```bash
# Найпростіший спосіб (якщо в app.py є app.run())
python app.py
# або
python3 app.py
```

Альтернативний спосіб через Flask CLI:

```bash
flask run
```

Якщо в коді є щось подібне:

```python
if __name__ == "__main__":
    app.run(debug=True)
```

то сервер зазвичай стартує на:  
**http://127.0.0.1:5000** або **http://localhost:5000**

---

Готово! Якщо з’явиться помилка — просто скопіюй її текст, і розберемося швидко.
Успіхів з проєктом! 🚀
```

Цей варіант легше читати, має чітку ієрархію, правильне форматування коду та підказки.














Звісно! Це комплексний проект для вивчення німецької мови ("German AI Tutor"), побудований як гібридний веб-додаток.

Він використовує класичний серверний підхід (Flask) у поєднанні з сучасною технологією HTMX для створення відчуття "живого" додатку (SPA - Single Page Application) без використання важких фреймворків на кшталт React чи Vue.

Ось детальний розбір архітектури та файлів.

🏗 Загальна Архітектура
Проект побудований за принципом Server-Driven UI (Інтерфейс, керований сервером).

Бекенд (Python/Flask) виконує всю важку роботу: логіку, роботу з базою даних, спілкування з AI (Gemini) та генерацію HTML.
Фронтенд (HTML/HTMX) — це переважно шаблони. HTMX дозволяє оновлювати частини сторінки (наприклад, картку слова або список текстів) без повного перезавантаження сторінки.
JavaScript (main.js) використовується лише там, де HTML безсилий: запис аудіо з мікрофону, візуалізація звуку та складна логіка програвання аудіо.
⚙️ Бекенд (Мозок проекту)
Ці файли відповідають за логіку, дані та API.

/app.py (Головний контролер)

Це серце додатку. Тут налаштовано веб-сервер Flask.
Роути (Routes): Визначає URL-адреси (наприклад, /, /library, /api/generate).
Контролери: Приймає запити від користувача, викликає потрібні сервіси та повертає або HTML-шаблони (через render_template), або JSON.
Адмінка: Налаштування панелі адміністратора (/admin) для керування контентом.
/services.py (Інтеграція з AI)

Це "робочі руки". app.py звертається сюди, коли треба щось розумне.
Gemini API: Функції generate_german_text (створення уроків), evaluate_audio_with_gemini (перевірка вимови), translate_word.
TTS (Text-to-Speech): Функції для озвучення тексту через Google Cloud або Azure.
/database.py

Відповідає за підключення до бази даних SQLite (data/app.db).
Містить схему бази даних (таблиці users, texts, vocabulary, sentences тощо).
/billing.py

Логіка списання "кредитів" (внутрішньої валюти) за використання AI функцій (генерація тексту, озвучка, перевірка голосу).
/utils/ (Утиліти)

Скрипти, які запускаються окремо (через термінал) для наповнення бази контентом.
generate_sentences.py: Генерує тисячі речень для рівнів A1-C2 через AI.
generate_audio.py: Масово озвучує ці речення.
🎨 Фронтенд (Обличчя проекту)
Фронтенд тут — це HTML-шаблони з вкрапленнями Jinja2 (логіка відображення) та атрибутами HTMX.

1. Основні шаблони (/templates/)
base.html: "Скелет" сайту. Містить <head>, підключення стилів, скриптів, навігаційне меню та контейнер для спливаючих повідомлень (toasts). Всі інші сторінки вставляються всередину цього файлу.
index.html: Головна сторінка з формою генерації нових текстів.
library.html: Список збережених текстів.
view.html: Сторінка читання тексту. Тут реалізована логіка кліку по словах для перекладу.
vocab.html: Сторінка словника (картки слів).
speaking.html: Сторінка тренажера вимови.
2. Частини інтерфейсу (/templates/partials/)
Це найважливіша частина для HTMX. Це шматочки HTML, які сервер надсилає для оновлення сторінки без перезавантаження.

speaking_card.html: Картка з реченням для озвучення. Коли ти натискаєш "Next", сервер надсилає лише цей шматок.
vocab_list.html: Список слів або сітка карток.
library_list.html: Список текстів (для пагінації та фільтрації).
3. Адмінка (/templates/admin/)
Шаблони для панелі адміністратора (редагування батчів речень, перегляд статистики кешування тощо).
4. Клієнтський JS (/static/js/main.js)
Цей файл відповідає за роботу з "залізом" браузера.
Запис аудіо: MediaRecorder, отримання доступу до мікрофону.
Візуалізація: Малює коло, що реагує на голос.
Детектор тиші: Автоматично зупиняє запис, коли користувач мовчить.
Анімація результатів: Малює красиві кола з оцінками (Pronunciation, Grammar).
🔄 Як це працює разом (Приклад: "Speaking")
Користувач заходить на /speaking.
Flask (app.py) віддає speaking.html.
HTMX всередині speaking.html робить запит на /speaking/next, отримує speaking_card.html і вставляє його в сторінку.
Користувач натискає кнопку мікрофону.
JS (main.js) починає запис, малює візуалізатор. Коли користувач замовкає, JS відправляє аудіо-файл на /api/evaluate_audio.
Flask отримує аудіо, передає його в services.py.
services.py відправляє аудіо в Gemini AI з промптом "Оціни вимову".
Gemini повертає JSON з оцінками та транскрипцією.
Flask повертає цей JSON назад у JS.
JS показує красивий Splash Screen з результатами та конфетті.
🗺 Карта проекту
Фронтенд: templates/, static/js/main.js, static/css/ (стилі вбудовані в HTML).
Бекенд: app.py, services.py, database.py, billing.py.
Дані: data/app.db (база), static/audio/ (кеш озвучки).
Це дуже ефективна архітектура для пет-проектів та стартапів, оскільки вона дозволяє писати складну логіку на Python, маючи при цьому швидкий та інтерактивний інтерфейс.