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
pip install flask flask-login flask-bcrypt python-dotenv flask-admin flask-sqlalchemy

# Google пакети
pip install google-generativeai
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