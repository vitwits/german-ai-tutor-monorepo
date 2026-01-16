# python generate_sentences.py A2 100



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
# 1. Визначаємо кореневу директорію (на рівень вище utils)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR) # Додаємо в path, щоб працювали імпорти з кореня (якщо знадобляться)

# 2. Явно вказуємо шлях до .env
load_dotenv(os.path.join(BASE_DIR, '.env'))

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("Error: GOOGLE_API_KEY not found in .env file")
    sys.exit(1)

client = genai.Client(api_key=API_KEY)

# --- КОНФІГУРАЦІЯ CEFR (Локальна копія для редагування) ---
CEFR_GUIDELINES = {
    "A1": "Sentences strictly 4-7 words (never under 4). Only Präsens. Maximize variety: 30-50 percent of sentences NOT starting with 'Ich' (use 'Das ist...', 'Es ist...', 'Mein/e... ist...', 'Wo...?'. 'Wie...?'. 'Heute ist...', 'Am...'). Always include in batches: questions (yes/no + wh-), negations (nicht/kein/keine), sein + Adj/Ort. Mix subjects (Ich/Du/Er/Sie/Es/Wir/Das/Mein Name). Topics: introductions, family/pets, home, hobbies, food, weather, routine, shopping, birthdays. Natural like Goethe A1 model sentences or textbooks (Netzwerk/Schritte).",
    "A2": "Sentences 6-11 words (avoid under 6 or over 12). Use Präsens + Perfekt (haben/sein dominant, especially sein for motion like fahren, gehen). Include connectors: und, aber, oder, weil (at least 20-40% with weil for reasons). Separable verbs (aufstehen, einkaufen, ausgehen, mitkommen). Full Akkusativ, introduce Dativ (mit, zu, von, bei, aus). Modal verbs in Präsens: können, wollen, müssen, sollen, mögen. Time expressions: gestern, morgen, oft, manchmal, jeden Tag/Morgen, am Wochenende. Vary starts: Am..., Gestern..., Ich habe/bin..., Manchmal..., Weil..., Mit... . Topics: daily routine, past weekend/activities, weather/seasons, food/preferences, simple reasons, hobbies/sport, shopping, travel basics. Natural, like Goethe A2 model sentences or textbooks (Netzwerk, Schritte) – everyday dialogues feel.",
    "B1": "Sentences 8-13 words (avoid under 8 or over 14). Mandatory subordinate clauses: weil, dass, wenn, obwohl (at least 40-60 percent include one). Dominant: Perfekt for past experiences, Präteritum for war/hatte/modals (konnte, wollte, musste). Basic Konjunktiv II: würde + Infinitiv for wishes; hätte/wäre/konnte for simple unreal/conditions/dreams. Introduce Futur I sparingly (werden + Infinitiv) for plans (10-20% max). Avoid or minimize Plusquamperfekt (only very simple like 'hatte vergessen' if needed – no complex comparisons). Comparative/superlative (besser als). Simple opinions: ich finde, dass...; ich träume davon, dass.... Vary starts: Obwohl..., Weil..., Wenn..., Ich habe..., Gestern.... Topics: experiences, reasons, opinions, dreams, simple future plans, everyday + light abstract. Natural, not overloaded – like Goethe B1 model sentences (focus on weil/dass/obwohl/wenn, basic Konjunktiv II, no heavy past-in-past).",
    "B2": "Sentences strictly 9-14 words (enforce: no less than 9, no more than 14). Vary syntax in batches of 5–10: include Passive (werden), relative clause (der/die/das/wo/wer), multi-part connector (zwar...aber, sowohl...als auch, entweder...oder, nicht nur...sondern auch) – one or two per sentence max. Use Plusquamperfekt simply (hatte + Partizip II). Konjunktiv II for hypotheticals. Futur I for plans/trends. Include occasional idioms/fixed expressions (es ist üblich, mit sich bringen, in der Lage sein). Topics: technology, culture, city life, environment, work, pros/cons. Natural, repeatable, exam-like (Goethe/telc B2 style) – clear, pronounceable, not overloaded.",
    "C1": "Sentences 12-18 words (strictly no less than 12, no more than 18). Use sophisticated structures: nominalization (die Tatsache, dass…; die Notwendigkeit; aufgrund eines Fehlers), complex subordinate clauses (In Anbetracht der Tatsache, dass…; Um…zu…, ist es unabdingbar, dass…). Include Konjunktiv I in reported speech or formal contexts (sei, habe). Full Passive and Zustandspassiv (wurde befreit, war befreit worden). Advanced connectors for cohesion and logic (insofern, folglich, zwar…dennoch, angesichts, aufgrund, infolge). Nuanced/fixed expressions (nicht verwunderlich, es gelingt, unabdingbar, sich Zeit nehmen). Topics: society, culture, work processes, environment, technology impacts, abstract pros/cons. Flow logical and cohesive, natural like advanced German texts or Goethe C1 models – sophisticated but not overly rhetorical yet.",
    "C2": "Sentences 14-20 words (strictly no more than 22, no less than 14). Mastery level: long, nuanced sentences with rhetorical devices (rhetorische Fragen, Ironie, Kontrastkonstruktionen, litotes, euphemism, hyperbole). Subtext and implicit criticism of society, trends, human nature. Use all tenses/moods fluently and stylistically (Konjunktiv I/II advanced, Futur II for assumptions, Plusquamperfekt narrative). Highly specific, academic, literary or journalistic vocabulary (grassierend, höhlt aus, wohlklingend, Zurschaustellung, Selbstoptimierungswelle, Muße, Kontemplation, unerschütterlich, keineswegs). Multi-part connectors (nicht nur … sondern auch, zwar … doch, mehr … als, allzu oft). Topics: social inequality, self-optimization culture, spirituality vs. reality, charity hypocrisy, human-animal relations, modern alienation. Flow elegant, cohesive, with critical depth – like high-level opinion articles, essays or literary commentary in German media (Zeit, FAZ Feuilleton, Philosophie Magazin)."
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
        "allowed_topics": BASE_TOPICS[:20],
        "abstraction": "none",
        "sentence_length": "short",
        "grammar": ["present", "basic verbs"]
    },
    "A2": {
        "allowed_topics": BASE_TOPICS[:39],
        "abstraction": "low",
        "sentence_length": "short-medium",
        "grammar": ["past", "modal verbs"]
    },
    "B1": {
        "allowed_topics": BASE_TOPICS[:58],
        "abstraction": "medium",
        "sentence_length": "medium",
        "grammar": ["subordinate clauses"]
    },
    "B2": {
        "allowed_topics": BASE_TOPICS[:83],
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