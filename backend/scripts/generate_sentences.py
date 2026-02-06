# python generate_sentences.py A1 100

import os
import sys
import csv
import json
import time
import random
import datetime
import re
import sqlite3
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Завантаження змінних середовища
# 1. Визначаємо кореневу директорію (на рівень вище utils)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR) # Додаємо в path, щоб працювали імпорти з кореня (якщо знадобляться)

# 2. Явно вказуємо шлях до .env
load_dotenv(os.path.join(BASE_DIR, '.env'))

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("Error: GEMINI_API_KEY not found in .env file")
    sys.exit(1)

client = genai.Client(api_key=API_KEY)

# ============================================================
# 📋 ЗАВАНТАЖЕННЯ ДАНИХ З БД (model_prompts)
# ============================================================
# Тут ми завантажуємо конфігурацію та промпти з Бази Даних:
# 1. CEFR Guidelines (рівні A1-C2)
# 2. Topics для кожного рівня (A1-C2 Topics)
# 3. General Guidelines (основний шаблон промпту)
# ============================================================

# --- ЗАПИС 1️⃣: CEFR GUIDELINES З БД ---
def load_cefr_guidelines_from_db():
    """Завантажує CEFR Guidelines з таблиці model_prompts в БД."""
    db_path = os.path.join(BASE_DIR, "data/app.db")
    
    if not os.path.exists(db_path):
        print(f"Warning: Database not found at {db_path}. Using empty guidelines.")
        return {}
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Точний query: шукаємо запис з точною назвою 'cefr_guidelines'
        cursor.execute("""
            SELECT prompt FROM model_prompts 
            WHERE name = 'cefr_guidelines'
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            guidelines_text = result[0]
            
            # Спроба 1: парсити як JSON
            try:
                guidelines = json.loads(guidelines_text)
                # ✅ ЗАПИС 1 ЗАВАНТАЖЕНО: CEFR Guidelines (рівні A1-C2)
                print(f"✅ Loaded CEFR Guidelines from database (JSON format)")
                return guidelines
            except json.JSONDecodeError:
                pass
            
            # Спроба 2: оцінити як Python об'єкт
            try:
                guidelines = eval(guidelines_text)
                if isinstance(guidelines, dict):
                    print(f"✅ Loaded CEFR Guidelines from database (Python dict format)")
                    return guidelines
            except:
                pass
            
            print("Warning: CEFR Guidelines found but could not be parsed. Using empty guidelines.")
            return {}
        else:
            print("❌ CEFR Guidelines not found in database at name='cefr_guidelines'")
            return {}
            
    except Exception as e:
        print(f"Error loading CEFR Guidelines from database: {e}")
        return {}

# --- ЗАПИСИ 2️⃣-7️⃣: TOPICS З БД (A1_TOPICS до C2_TOPICS) ---
def load_topics_from_db(level):
    """Завантажує Topics для конкретного рівня з БД.
    Обробляє як JSON формат, так і звичайні об'єкти (списки)."""
    db_path = os.path.join(BASE_DIR, "data/app.db")
    
    if not os.path.exists(db_path):
        return []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Точний query: шукаємо запис з точною назвою '{level}_topics' (нижній регістр)
        topic_name = f"{level.lower()}_topics"
        cursor.execute("""
            SELECT prompt FROM model_prompts 
            WHERE name = ?
            LIMIT 1
        """, (topic_name,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            topics_text = result[0]
            
            # Спроба 1: парсити як JSON
            try:
                topics = json.loads(topics_text)
                if isinstance(topics, list):
                    print(f"✅ Loaded {level.upper()}_TOPICS from database (JSON format, {len(topics)} items)")
                    return topics
            except json.JSONDecodeError:
                pass
            
            # Спроба 2: оцінити як Python об'єкт
            try:
                topics = eval(topics_text)
                if isinstance(topics, list):
                    print(f"✅ Loaded {level.upper()}_TOPICS from database (Python format, {len(topics)} items)")
                    return topics
            except:
                pass
        
        print(f"❌ {level.upper()}_TOPICS not found in database at name='{level.lower()}_topics'")
        return []
            
    except Exception as e:
        print(f"Error loading {level} topics from database: {e}")
        return []

# --- ЗАПИС 8️⃣: GENERAL GUIDELINES PROMPT TEMPLATE З БД ---
def load_prompt_template_from_db(template_name):
    """Завантажує шаблон промпту з БД.
    
    Шаблон зберігається в model_prompts з плейсхолдерами:
    {count}, {level}, {topics_str}, {level_rules}
    які будуть замінені на реальні значення при виконанні.
    """
    db_path = os.path.join(BASE_DIR, "data/app.db")
    
    if not os.path.exists(db_path):
        return None
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Точний query: шукаємо запис з точною назвою '{template_name}' (нижній регістр)
        cursor.execute("""
            SELECT prompt FROM model_prompts 
            WHERE name = ?
            LIMIT 1
        """, (template_name.lower(),))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    except Exception as e:
        print(f"Error loading prompt template '{template_name}': {e}")
        return None
    
    if result:
        print(f"✅ Loaded prompt template '{template_name}' from database")
        print(f"   📝 Template length: {len(result[0])} chars")
        print(f"   📝 Placeholders found: {', '.join([p for p in ['{count}', '{level}', '{topics_str}', '{level_rules}'] if p in result[0]])}")
        return result[0]
    else:
        print(f"❌ Prompt template '{template_name}' not found in database")
        return None

# ============================================================
# 🔄 ІНІЦІАЛІЗАЦІЯ: Завантаження 8 записів з БД
# ============================================================

# ЗАПИС 1️⃣: CEFR Guidelines (вміст гайдлайнів для рівнів A1-C2)
CEFR_GUIDELINES = load_cefr_guidelines_from_db()

# ЗАПИСИ 2️⃣-7️⃣: Topics для кожного рівня
# ЗАПИС 2️⃣: A1_TOPICS
A1_TOPICS = load_topics_from_db("A1")
# ЗАПИС 3️⃣: A2_TOPICS
A2_TOPICS = load_topics_from_db("A2")
# ЗАПИС 4️⃣: B1_TOPICS
B1_TOPICS = load_topics_from_db("B1")
# ЗАПИС 5️⃣: B2_TOPICS
B2_TOPICS = load_topics_from_db("B2")
# ЗАПИС 6️⃣: C1_TOPICS
C1_TOPICS = load_topics_from_db("C1")
# ЗАПИС 7️⃣: C2_TOPICS
C2_TOPICS = load_topics_from_db("C2")

LEVEL_RULES = {
    "A1": A1_TOPICS,
    "A2": A2_TOPICS,
    "B1": B1_TOPICS,
    "B2": B2_TOPICS,
    "C1": C1_TOPICS,
    "C2": C2_TOPICS
}

def clean_json_response(text):
    """Очищає відповідь від Markdown блоків."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text

def generate_batch(level, count, topics_subset):
    """Генерує пакет речень."""
    
    level_rules = CEFR_GUIDELINES.get(level.upper(), "")
    topics_str = ", ".join(topics_subset)
    
    # 📋 Використовуємо ЗАПИС 8️⃣: GENERAL GUIDELINES (основний шаблон промпту)
    # Це шаблон з плейсхолдерами, який буде повний промпт
    prompt_template = load_prompt_template_from_db("general_guidelines")
    
    if not prompt_template:
        print("Error: Prompt template 'general_guidelines' not found in database")
        return []
    
    # Підставляємо значення у шаблон
    prompt = prompt_template.format(
        count=count,
        level=level.upper(),
        topics_str=topics_str,
        level_rules=level_rules
    )
    
    # Підставляємо значення у шаблон (count, level, topics_str, level_rules)
    prompt = prompt_template.format(
        count=count,
        level=level.upper(),
        topics_str=topics_str,
        level_rules=level_rules
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=1.37 if level.upper() == "A1" else 1.1,
            )
        )
        
        cleaned_text = clean_json_response(response.text)
        data = json.loads(cleaned_text)
        
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "sentences" in data:
            return data["sentences"]
        else:
            return []
            
    except Exception as e:
        print(f"Error generating batch: {e}")
        return []

def main():
    # 1. Парсинг аргументів
    if len(sys.argv) < 3:
        print("Usage: python generate_sentences.py <level> <count>")
        print("Example: python generate_sentences.py A2 100")
        sys.exit(1)

    level = sys.argv[1].upper()
    try:
        total_count = int(sys.argv[2])
    except ValueError:
        print("Error: Count must be a number.")
        sys.exit(1)

    if level not in CEFR_GUIDELINES:
        print(f"Warning: Level {level} not found in guidelines. Using default rules or generic prompt.")

    # 📋 Використовуємо ЗАПИСИ 2️⃣-7️⃣: Topics для обраного рівня
    # LEVEL_RULES містить посилання на A1_TOPICS, A2_TOPICS, ... C2_TOPICS (усі завантажені з БД)
    available_topics = LEVEL_RULES.get(level, A2_TOPICS)

    # 2. Підготовка файлу
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sentences_{level}_{timestamp}.csv"
    
    print(f"--- Starting generation ---")
    print(f"Level: {level}")
    print(f"Target: {total_count} sentences")
    print(f"Output file: {filename}")
    print(f"---------------------------")

    # 3. Генерація пакетами (щоб не перевантажити контекст і отримати валідний JSON)
    BATCH_SIZE = 20
    generated_count = 0
    
    # Відкриваємо файл відразу для запису
    with open(filename, mode='w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['de', 'uk', 'en', 'topic', 'level']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        while generated_count < total_count:
            # Визначаємо розмір поточного пакету (останній може бути меншим)
            current_batch_size = min(BATCH_SIZE, total_count - generated_count)
            
            # Вибираємо випадкові теми
            if len(available_topics) >= current_batch_size:
                batch_topics = random.sample(available_topics, current_batch_size)
            else:
                batch_topics = random.choices(available_topics, k=current_batch_size)
            
            print(f"Generating batch {generated_count + 1}-{generated_count + current_batch_size}...")
            
            sentences = generate_batch(level, current_batch_size, batch_topics)
            
            if not sentences:
                print("Failed to generate batch. Retrying in 2 seconds...")
                time.sleep(2)
                continue

            # Запис у файл
            for s in sentences:
                # Нормалізація ключів (іноді модель може дати 'ua' замість 'uk')
                uk_text = s.get('uk') or s.get('ua') or ""
                
                row = {
                    'de': s.get('de', ''),
                    'uk': uk_text,
                    'en': s.get('en', ''),
                    'topic': s.get('topic', ''),
                    'level': level
                }
                writer.writerow(row)
            
            generated_count += len(sentences)
            
            # Невелика пауза, щоб бути ввічливим до API
            time.sleep(0.5)

    print(f"\nDone! Successfully generated {generated_count} sentences.")
    print(f"Saved to: {os.path.abspath(filename)}")

if __name__ == "__main__":
    main()