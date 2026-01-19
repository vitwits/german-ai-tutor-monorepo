import sqlite3
import os

DB_PATH = 'data/app.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists('data'):
        os.makedirs('data')
    
    with get_db() as conn:
        # --- Міграції ---
        # 1. Додаємо колонку мови інтерфейсу до users
        try:
            conn.execute('ALTER TABLE users ADD COLUMN interface_language TEXT DEFAULT "ukr"')
            conn.commit()
        except sqlite3.OperationalError:
            pass # Колонка вже існує

        # 1.2 Додаємо колонку кредитів (Billing)
        try:
            conn.execute('ALTER TABLE users ADD COLUMN credits REAL DEFAULT 1000.0')
            conn.commit()
        except sqlite3.OperationalError:
            pass

        # 1.1 Додаємо колонку рівня мови (Global Level)
        try:
            conn.execute('ALTER TABLE users ADD COLUMN level TEXT DEFAULT "A2"')
            conn.commit()
        except sqlite3.OperationalError:
            pass

        # 1.3 Додаємо колонку is_admin
        try:
            conn.execute('ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0')
            conn.commit()
            print("LOG: Column 'is_admin' added to users table.")
        except sqlite3.OperationalError as e:
            # Ігноруємо помилку, якщо колонка вже існує
            pass 

        # Таблиця користувачів
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            interface_language TEXT DEFAULT 'ukr',
            level TEXT DEFAULT 'A2',
            credits REAL DEFAULT 1000.0,
            is_admin INTEGER DEFAULT 0
        )''')
        
        # Таблиця текстів
        conn.execute('''CREATE TABLE IF NOT EXISTS texts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT,
            level TEXT,
            content_json TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')
        

        # Таблиця слів словника
        conn.execute('''CREATE TABLE IF NOT EXISTS vocabulary (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            text_id TEXT,
            origin TEXT,
            display TEXT,
            ua TEXT,
            en TEXT,
            ctx TEXT,
            is_favorite INTEGER DEFAULT 0,
            
            -- НОВІ ПОЛЯ ДЛЯ ТОЧНОЇ ПОЗИЦІЇ
            sentence_index INTEGER, -- Номер речення (0, 1, 2...)
            start_index INTEGER,    -- Початок виділення (символ)
            end_index INTEGER,      -- Кінець виділення
            
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')

        # 2. Оновлюємо схему кешу граматики
        try:
            # Перевіряємо наявність нової колонки 'language'
            conn.execute('SELECT language FROM grammar_explanations LIMIT 1')
        except sqlite3.OperationalError:
            # Якщо колонки немає, це стара схема, тому перестворюємо таблицю
            conn.execute('DROP TABLE IF EXISTS grammar_explanations')

        # Таблиця кешу пояснень граматики
        conn.execute('''CREATE TABLE IF NOT EXISTS grammar_explanations (
            text_id TEXT,
            sentence_index INTEGER,
            language TEXT,
            explanation TEXT,
            PRIMARY KEY (text_id, sentence_index, language)
        )''')

        # 3. Міграції для налаштувань відображення (View Settings)
        try:
            conn.execute('ALTER TABLE users ADD COLUMN library_view_mode TEXT DEFAULT "list"')
            conn.execute('ALTER TABLE users ADD COLUMN library_per_page INTEGER DEFAULT 20')
            conn.execute('ALTER TABLE users ADD COLUMN vocab_view_mode TEXT DEFAULT "list"')
            conn.execute('ALTER TABLE users ADD COLUMN vocab_per_page INTEGER DEFAULT 20')
        except sqlite3.OperationalError:
            pass # Колонка вже існує

        # 4. Міграція для рівня слів
        try:
            conn.execute('ALTER TABLE vocabulary ADD COLUMN level TEXT')
        except sqlite3.OperationalError:
            pass

        # 6. Міграція для улюблених текстів (Favorites)
        try:
            conn.execute('ALTER TABLE texts ADD COLUMN is_favorite INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass

        # 7. Міграція для квізів (Quiz)
        try:
            conn.execute('ALTER TABLE texts ADD COLUMN quiz_json TEXT')
        except sqlite3.OperationalError:
            pass

        # Таблиця результатів квізів
        conn.execute('''CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            text_id TEXT NOT NULL,
            score INTEGER,
            total_questions INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (text_id) REFERENCES texts (id)
        )''')

        # 5. Таблиці для генератора речень (Admin Tool)
        conn.execute('''CREATE TABLE IF NOT EXISTS sentence_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            level TEXT,
            target_count INTEGER,
            processed_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending', -- generating_text, text_ready, generating_audio, completed, error
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        conn.execute('''CREATE TABLE IF NOT EXISTS temp_sentences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER,
            de TEXT,
            en TEXT,
            uk TEXT,
            topic TEXT,
            FOREIGN KEY (batch_id) REFERENCES sentence_batches (id) ON DELETE CASCADE
        )''')

        conn.commit()