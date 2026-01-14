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
        # Таблиця користувачів
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
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

        # Таблиця кешу пояснень граматики
        conn.execute('''CREATE TABLE IF NOT EXISTS grammar_explanations (
            text_id TEXT,
            sentence_index INTEGER,
            explanation TEXT,
            PRIMARY KEY (text_id, sentence_index)
        )''')
        conn.commit()