# python generate_audio.py file.csv

import os
import sys
import csv
import sqlite3
import random
from dotenv import load_dotenv
from google.cloud import texttospeech

# 1. Налаштування шляхів
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, '.env'))

# 2. Google конфігурація
if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    print("Error: GOOGLE_APPLICATION_CREDENTIALS not found in .env")
    sys.exit(1)

# 3. Шляхи до БД та аудіо
DB_PATH = os.path.join(BASE_DIR, 'data', 'app.db')
STATIC_AUDIO_DIR = os.path.join(BASE_DIR, 'static', 'audio', 'sentences')

# 4. Голоси (Gemini / Chirp)
VOICES = {
    'uk': ["uk-UA-Chirp3-HD-Leda", "uk-UA-Chirp3-HD-Sadachbia"],
    'en': ["en-US-Chirp-HD-O", "en-US-Chirp3-HD-Alnilam"],
    'de': ["de-DE-Chirp3-HD-Alnilam", "de-DE-Chirp3-HD-Leda"]
}

def generate_file(text, lang, filepath):
    # Створюємо папку, якщо немає
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    client = texttospeech.TextToSpeechClient()
    
    # Вибір голосу 50/50
    voice_name = random.choice(VOICES[lang])
    language_code = voice_name[:5]
    
    s_input = texttospeech.SynthesisInput(text=text)
    
    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=voice_name
    )
    
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.OGG_OPUS # <--- Змінюємо тут
    )
    
    try:
        response = client.synthesize_speech(
            input=s_input, voice=voice, audio_config=audio_config
        )
        
        with open(filepath, "wb") as out:
            out.write(response.audio_content)
        return True
    except Exception as e:
        print(f"Error synthesizing {lang} ({voice_name}): {e}")
        return False

def init_db():
    if not os.path.exists(os.path.dirname(DB_PATH)):
        os.makedirs(os.path.dirname(DB_PATH))
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Створення таблиці, якщо не існує
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sentences (
            id INTEGER PRIMARY KEY,
            text_de TEXT,
            text_en TEXT,
            text_uk TEXT,
            audio_de TEXT,
            audio_en TEXT,
            audio_uk TEXT,
            level TEXT,
            topic TEXT
        )
    ''')
    conn.commit()
    return conn

def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_audio.py <csv_file>")
        sys.exit(1)
        
    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        sys.exit(1)
        
    conn = init_db()
    cursor = conn.cursor()
    
    # Отримуємо останній ID
    cursor.execute("SELECT MAX(id) FROM sentences")
    row = cursor.fetchone()
    start_id = (row[0] if row[0] is not None else 0) + 1
    
    rows_to_insert = []
    current_id = start_id
    
    print(f"Starting generation from ID: {current_id}")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            de = row.get('de', '').strip()
            uk = row.get('uk', '').strip()
            en = row.get('en', '').strip()
            topic = row.get('topic', '').strip()
            level = row.get('level', '').strip() # e.g. "A1"
            
            if not de: continue
            
            # Формування шляхів
            level_lower = level.lower()
            file_prefix = f"{current_id:04d}"
            
            rel_folder = level_lower
            
            # Відносні шляхи для БД
            path_de_rel = f"{rel_folder}/{file_prefix}_de.ogg"
            path_en_rel = f"{rel_folder}/{file_prefix}_en.ogg"
            path_uk_rel = f"{rel_folder}/{file_prefix}_uk.ogg"
            
            # Абсолютні шляхи для запису
            path_de_abs = os.path.join(STATIC_AUDIO_DIR, path_de_rel)
            path_en_abs = os.path.join(STATIC_AUDIO_DIR, path_en_rel)
            path_uk_abs = os.path.join(STATIC_AUDIO_DIR, path_uk_rel)
            
            print(f"[{current_id}] Generating audio for: {de[:30]}...")
            
            # Генерація
            success = True
            if not generate_file(de, 'de', path_de_abs): success = False
            if success and not generate_file(en, 'en', path_en_abs): success = False
            if success and not generate_file(uk, 'uk', path_uk_abs): success = False
            
            if success:
                rows_to_insert.append((
                    current_id,
                    de, en, uk,
                    path_de_rel, path_en_rel, path_uk_rel,
                    level, topic
                ))
                current_id += 1
            else:
                print(f"Skipping row {current_id} due to errors.")
                
    # Вставка в БД
    if rows_to_insert:
        print(f"Inserting {len(rows_to_insert)} rows into database...")
        cursor.executemany('''
            INSERT INTO sentences (id, text_de, text_en, text_uk, audio_de, audio_en, audio_uk, level, topic)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', rows_to_insert)
        conn.commit()
        print("Success!")
    else:
        print("No rows processed.")
        
    conn.close()

if __name__ == "__main__":
    main()