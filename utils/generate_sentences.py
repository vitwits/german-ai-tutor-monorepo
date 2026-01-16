import os
import sys
import csv
import json
import time
import random
import datetime
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Завантаження змінних середовища
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    print("Error: GOOGLE_API_KEY not found in .env file")
    sys.exit(1)

client = genai.Client(api_key=API_KEY)

# --- КОНФІГУРАЦІЯ CEFR (Локальна копія для редагування) ---
CEFR_GUIDELINES = {
    "A1": "Use natural but simple sentences (5-9 words). Avoid 3-word sentences. Structure: Subject-Verb-Complement/Object. Present tense. Use common nouns and basic adjectives (e.g., instead of 'Das Kino ist klein', use 'Das kleine Kino ist sehr modern').",
    "A2": "Sentences 8-12 words. Avoid 6-word sentences. Use simple connectors (und, aber, oder). Use Perfekt for past tense. Topics: shopping, work, immediate environment.",
    "B1": "Sentences 10-15 words. MUST use subordinate clauses (weil, wenn, dass). Use Präteritum for modals. Introduce simple abstract topics. Start using distinct connecting words.",
    "B2": "Average length: 13-16 words. STRICT LIMIT: No sentence over 18 words and less than 13. Focus on syntactic variety: use Passive voice in one sentence, a Relative clause in another, and ONE multi-part connector (e.g., 'zwar... aber') in a third. DO NOT combine these in a single sentence. Include one idiom. Use abstract vocabulary, but keep the flow concise and teacher-like.",
    "C1": "Sophisticated structure (14-18 words). No sentence over 19 words and less than 13. Use nominalization, complex syntax, fixed idiomatic expressions, and nuances. Text must flow logically with high cohesion. Advanced vocabulary is required.",
    "C2": "Mastery level. Long, nuanced sentences (16-22 words). No sentence over 22 words and less than 15. Use rhetorical devices, irony, and implicit meanings. Vocabulary must be highly specific, academic, or literary depending on context."
}

# --- СПИСОК ТЕМ (100+) ---
BASE_TOPICS = [
    # A1 — concrete, personal, here-and-now
    "Daily Routine",
    "Family & Relationships",
    "Friendship",
    "Pets & Animals",
    "Food & Cooking",
    "Fast Food",
    "Shopping & Groceries",
    "Gifts & Presents",
    "Birthdays",
    "Weather & Seasons",
    "Hobbies & Free Time",
    "Housing & Furniture",
    "City Life",
    "Public Transport",
    "Travel & Transport",
    "Restaurants & Cafes",
    "Coffee Culture",
    "Cleaning & Chores",
    "Sleep & Dreams",
    "Weekend Activities",

    # A2 — extended daily life
    "Work & Career",
    "Education & School",
    "Health & Fitness",
    "Sports & Games",
    "Running",
    "Team Sports",
    "Movies & TV Series",
    "Music & Concerts",
    "Books & Literature",
    "Online Shopping",
    "Grocery Prices",
    "Food Delivery",
    "Hotels & Accommodation",
    "Driving & Cars",
    "Bicycles & Cycling",
    "Swimming & Water Sports",
    "Holidays & Vacations",
    "Baking",
    "Vegetarianism",

    # B1 — experience, plans, opinions
    "Childhood Memories",
    "Future Plans",
    "Dreams & Ambitions",
    "Learning Languages",
    "Technology & Internet",
    "Social Media",
    "Mobile Apps",
    "Photography",
    "Gardening",
    "Home Improvement",
    "Stress & Relaxation",
    "Meditation",
    "Yoga",
    "Gym & Workout",
    "Board Games",
    "Video Games",
    "Fashion & Clothing",
    "Writing",
    "Journaling",

    # B2 — abstraction, society, systems
    "Money & Finance",
    "Productivity",
    "Time Management",
    "Leadership",
    "Teamwork",
    "Communication Skills",
    "Public Speaking",
    "News & Media",
    "Advertising",
    "Celebrities",
    "Influencers",
    "Privacy & Security",
    "Smartphones",
    "Laptops & Computers",
    "Artificial Intelligence",
    "Robots",
    "Virtual Reality",
    "Recycling",
    "Climate Change",
    "Nature & Environment",
    "Design",
    "Architecture",
    "Psychology & Emotions",
    "Conflict & Resolution",
    "Cultural Differences",

    # C1/C2 — abstract, global, ethical
    "Politics & Society",
    "History & Culture",
    "Traditions & Festivals",
    "Philosophy",
    "Religion & Spirituality",
    "Science & Innovation",
    "Space & Universe",
    "Global Issues",
    "Poverty & Wealth",
    "Equality",
    "Justice",
    "Law & Order",
    "Crime & Punishment",
    "Safety",
    "Emergency Services",
    "Healthcare System",
    "Volunteering",
    "Charity",
    "Art & Museums",
    "Countryside Life",
    "Painting & Drawing",
    "DIY & Crafts",
    "Architecture"
]

LEVEL_RULES = {
    "A1": {
        "allowed_topics": BASE_TOPICS[:6],
        "abstraction": "none",
        "sentence_length": "short",
        "grammar": ["present", "basic verbs"]
    },
    "A2": {
        "allowed_topics": BASE_TOPICS[:9],
        "abstraction": "low",
        "sentence_length": "short-medium",
        "grammar": ["past", "modal verbs"]
    },
    "B1": {
        "allowed_topics": BASE_TOPICS[:12],
        "abstraction": "medium",
        "sentence_length": "medium",
        "grammar": ["subordinate clauses"]
    },
    "B2": {
        "allowed_topics": BASE_TOPICS[:14],
        "abstraction": "high",
        "sentence_length": "long",
        "grammar": ["passive", "Konjunktiv II"]
    },
    "C1": {
        "allowed_topics": BASE_TOPICS,
        "abstraction": "very high",
        "sentence_length": "long",
        "grammar": ["nominalization", "complex syntax"]
    },
    "C2": {
        "allowed_topics": BASE_TOPICS,
        "abstraction": "free",
        "sentence_length": "very long",
        "grammar": ["stylistic variation", "rhetoric"]
    }
}



def clean_json_response(text):
    """Очищає відповідь від Markdown блоків."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text

def generate_batch(level, count, topics_subset):
    """Генерує пакет речень."""
    
    level_rules = CEFR_GUIDELINES.get(level.upper(), CEFR_GUIDELINES["A2"])
    
    # Формуємо список тем для цього батчу
    topics_str = ", ".join(topics_subset)

    prompt = f"""
    Role: Expert German Linguist.
    Task: Generate exactly {count} unique German sentences.
    Level: {level.upper()}
    
    Use these topics (one sentence per topic if possible):
    {topics_str}
    
    STRICT CEFR RULES for {level.upper()}:
    {level_rules}
    
    Requirements:
    1. Sentences must be grammatically correct and sound natural.
    2. Provide translations in Ukrainian (uk) and English (en).
    3. Output must be a valid JSON list of objects.
    
    JSON Format:
    [
        {{
            "de": "German sentence",
            "uk": "Ukrainian translation",
            "en": "English translation",
            "topic": "Topic used"
        }}
    ]
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.85
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

    # Визначаємо доступні теми для рівня
    if level in LEVEL_RULES:
        available_topics = LEVEL_RULES[level]["allowed_topics"]
    else:
        available_topics = BASE_TOPICS

    # 2. Підготовка файлу
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sentences_{level}_{timestamp}.csv"
    
    print(f"--- Starting generation ---")
    print(f"Level: {level}")
    print(f"Target: {total_count} sentences")
    print(f"Output file: {filename}")
    print(f"---------------------------")

    # 3. Генерація пакетами (щоб не перевантажити контекст і отримати валідний JSON)
    BATCH_SIZE = 10
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