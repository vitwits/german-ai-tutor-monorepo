import os
import sys
import sqlite3
import random
from dotenv import load_dotenv
from google.cloud import texttospeech
import azure.cognitiveservices.speech as speechsdk

# 1. Налаштування шляхів
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, '.env'))

# 2. Google конфігурація
creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if not creds_path:
    print("Error: GOOGLE_APPLICATION_CREDENTIALS not found in .env")
    sys.exit(1)

if not os.path.isabs(creds_path):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(BASE_DIR, creds_path)

# Azure конфігурація
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")

# 3. Шляхи
DB_PATH = os.path.join(BASE_DIR, 'data', 'app.db')
STATIC_DIR = os.path.join(BASE_DIR, 'static', 'audio', 'feedback')

# 4. Голоси (Azure для UK, Gemini/Chirp для EN)
VOICES = {
    'uk_azure': ["uk-UA-PolinaNeural", "uk-UA-OstapNeural"],
    'uk_google': ["uk-UA-Chirp3-HD-Leda", "uk-UA-Chirp3-HD-Sadachbia"],
    'en_google': ["en-US-Chirp-HD-O", "en-US-Chirp3-HD-Alnilam"]
}

# 5. Новий пул фраз
FEEDBACK_POOL = {
    "1-10": {
        "uk": [
            "Не здавайся, спробуй ще!", "Початок завжди складний.", "Давай ще раз повільно.",
            "Спробуємо знову разом?", "Перший крок зроблено!", "Трохи більше практики.",
            "Нічого, це лише початок.", "Ти обов'язково навчишся.", "Головне — не зупинятися.", "Давай спробуємо інше?"
        ],
        "en": [
            "Don't give up, try again!", "Starting is always hard.", "Let's try slowly again.",
            "Shall we try together?", "The first step is taken!", "A little more practice.",
            "It's okay, just a start.", "You will definitely learn.", "Just keep moving forward.", "Let's try once more?"
        ]
    },
    "11-20": {
        "uk": [
            "Вже краще, продовжуй!", "Бачу твої зусилля.", "Маленькими кроками вперед.",
            "Ти на правильному шляху.", "Не зупиняйся зараз.", "Кожна спроба важлива.",
            "Ще трішки уваги.", "Ти можеш краще!", "Рухаємося далі.", "Практика робить дива."
        ],
        "en": [
            "Getting better, keep going!", "I see your effort.", "Small steps forward.",
            "You're on the right track.", "Don't stop now.", "Every try counts.",
            "A bit more focus.", "You can do better!", "Let's keep moving.", "Practice makes wonders."
        ]
    },
    "21-30": {
        "uk": [
            "Впевненість прийде з часом.", "Хороша спроба!", "Ти робиш прогрес.",
            "Слухай уважно і повтори.", "Бачу позитивні зміни.", "Ти стаєш сильнішим.",
            "Продовжуй тренуватися.", "Вже є перші успіхи!", "Крок за кроком.", "Ти молодець, що намагаєшся."
        ],
        "en": [
            "Confidence comes with time.", "Good try!", "You're making progress.",
            "Listen closely and repeat.", "I see positive changes.", "You're getting stronger.",
            "Keep on practicing.", "First successes are here!", "Step by step.", "Great job for trying."
        ]
    },
    "31-40": {
        "uk": [
            "Це вже цікаво!", "Ти помітно прогресуєш.", "Ще трішки зусиль.",
            "Гарна робота, не зупиняйся.", "Твоя вимова покращується.", "Вже майже вийшло!",
            "Тримай ритм!", "Ти на вірному шляху.", "Досить непогано!", "Твій темп вражає."
        ],
        "en": [
            "That's getting interesting!", "Visible progress here.", "A little more effort.",
            "Good work, keep going.", "Your pronunciation improves.", "You're almost there!",
            "Keep the rhythm!", "You are on track.", "Quite good indeed!", "Your pace is impressive."
        ]
    },
    "41-50": {
        "uk": [
            "Половина шляху позаду!", "Дуже гідний результат.", "Ти вже багато знаєш.",
            "Це звучить переконливо.", "Гарний старт сесії!", "Ти старанно працюєш.",
            "Мені подобається твій темп.", "Ще трохи практики.", "Ти рухаєшся вгору.", "Так тримати!"
        ],
        "en": [
            "Halfway there!", "A very decent result.", "You know a lot already.",
            "That sounds convincing.", "Great session start!", "You're working hard.",
            "I like your pace.", "Just a bit more practice.", "You're moving up.", "Keep it up!"
        ]
    },
    "51-60": {
        "uk": [
            "Впевнений результат!", "Ти вже розумієш логіку.", "Справді непогана робота.",
            "Ти звучиш значно краще.", "Гарний рівень знань.", "Ти мене радуєш!",
            "Цікавий підхід до мови.", "Більше ніж половина!", "Відчуваєш свій прогрес?", "Це твердий результат."
        ],
        "en": [
            "A solid result!", "You get the logic now.", "Really good work.",
            "You sound much better.", "Good level of knowledge.", "You make me happy!",
            "Interesting language approach.", "More than half done!", "Feel your progress?", "That's a solid score."
        ]
    },
    "61-70": {
        "uk": [
            "Це вже високий рівень!", "Ти майже професіонал.", "Звучить дуже природно.",
            "Я вражений твоєю працею.", "Ти робиш це легко.", "Чудовий прогрес сьогодні.",
            "Ти відчуваєш мову.", "Гарна інтонація!", "Це успіх!", "Ти справжній молодець."
        ],
        "en": [
            "This is high level!", "You're almost a pro.", "Sounds very natural.",
            "Impressed with your work.", "You make it look easy.", "Great progress today.",
            "You feel the language.", "Good intonation!", "It's a success!", "You're doing great."
        ]
    },
    "71-80": {
        "uk": [
            "Майже ідеально!", "Ти звучиш дуже впевнено.", "Блискучий результат!",
            "Твоя німецька оживає.", "Чудова робота сьогодні.", "Ти мене дивуєш!",
            "Високий пілотаж!", "Ще крок до досконалості.", "Пишаюся твоїми успіхами.", "Ти на висоті!"
        ],
        "en": [
            "Almost perfect!", "You sound very confident.", "A brilliant result!",
            "Your German is alive.", "Wonderful work today.", "You surprise me!",
            "Top-notch performance!", "One step to perfection.", "Proud of your success.", "You're at the top!"
        ]
    },
    "81-90": {
        "uk": [
            "Фантастичний переклад!", "Майже як носій мови.", "Вражаюча точність.",
            "Ти справжній майстер.", "Неймовірна робота!", "Просто бездоганно.",
            "Ти надихаєш!", "Дуже професійно.", "Це рівень експерта.", "Чудово впоралися!"
        ],
        "en": [
            "Fantastic translation!", "Almost like a native.", "Impressive accuracy.",
            "You're a true master.", "Incredible work!", "Simply flawless.",
            "You're an inspiration!", "Very professional.", "Expert level achieved.", "You handled it perfectly!"
        ]
    },
    "91-100": {
        "uk": [
            "Абсолютний тріумф!", "Ти — справжній геній!", "Ідеально до дрібниць.",
            "Це було бездоганно.", "Ти вже як німець!", "Найвищий бал!",
            "Просто неймовірно.", "Краще не буває!", "Ти підкорив цю фразу.", "Справжній мовний талант!"
        ],
        "en": [
            "Absolute triumph!", "You're a true genius!", "Perfect in every detail.",
            "That was flawless.", "You're like a native!", "The highest score!",
            "Simply incredible.", "Doesn't get any better!", "You mastered this phrase.", "A real language talent!"
        ]
    }
}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Створення таблиці feedback
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id TEXT PRIMARY KEY,
            text TEXT,
            file_path TEXT,
            language TEXT,
            category TEXT,
            min_score INTEGER,
            max_score INTEGER
        )
    ''')
    conn.commit()
    return conn

def generate_audio(text, lang_code, filepath, provider='google'):
    # Створюємо папку
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    if provider == 'azure':
        # --- AZURE IMPLEMENTATION ---
        if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
            print("Error: Azure credentials not found")
            return False
            
        speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
        
        # Вибір голосу 50/50
        voice_name = random.choice(VOICES['uk_azure'])
        speech_config.speech_synthesis_voice_name = voice_name
        
        # Формат OggOpus (сумісний з HTML5 audio)
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Ogg24Khz16BitMonoOpus
        )
        
        audio_config = speechsdk.audio.AudioOutputConfig(filename=filepath)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        
        result = synthesizer.speak_text_async(text).get()
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return True
        else:
            print(f"Azure Error generating {filepath}: {result.cancellation_details.reason}")
            return False
            
    else:
        # --- GOOGLE IMPLEMENTATION (Existing) ---
        client = texttospeech.TextToSpeechClient()
        voice_key = 'uk_google' if lang_code == 'uk' else 'en_google'
        voice_name = random.choice(VOICES[voice_key])
        language_code = voice_name[:5]
        
        s_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.OGG_OPUS
        )
        
        try:
            response = client.synthesize_speech(input=s_input, voice=voice, audio_config=audio_config)
            with open(filepath, "wb") as out:
                out.write(response.audio_content)
            return True
        except Exception as e:
            print(f"Google Error generating {filepath}: {e}")
            return False

def main():
    conn = init_db()
    cursor = conn.cursor()
    
    # Очищення таблиці
    print("Clearing feedback table...")
    cursor.execute("DELETE FROM feedback")
    conn.commit()
    
    print("Starting feedback generation...")
    
    for score_range, langs in FEEDBACK_POOL.items():
        min_s, max_s = map(int, score_range.split('-'))
        
        for lang, phrases in langs.items():
            if lang == 'title': continue # Skip title field
            
            for i, text in enumerate(phrases):
                # Формат: uk_1-10_01_v1.ogg
                base_name = f"{lang}_{score_range}_{i+1:02d}"
                
                # --- Версія 1 (Google) ---
                # Для EN це єдина версія, для UK - перша
                filename_v1 = f"{base_name}_v1.ogg"
                path_v1_abs = os.path.join(STATIC_DIR, lang, filename_v1)
                path_v1_rel = f"feedback/{lang}/{filename_v1}"
                
                print(f"Generating {filename_v1}...")
                if generate_audio(text, lang, path_v1_abs, provider='google'):
                    cursor.execute('''
                        INSERT INTO feedback (id, text, file_path, language, category, min_score, max_score)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (filename_v1.replace('.ogg',''), text, path_v1_rel, lang, 'common', min_s, max_s))
                
                # --- Версія 2 (Azure) - Тільки для UK ---
                if lang == 'uk':
                    filename_v2 = f"{base_name}_v2.ogg"
                    path_v2_abs = os.path.join(STATIC_DIR, lang, filename_v2)
                    path_v2_rel = f"feedback/{lang}/{filename_v2}"
                    
                    print(f"Generating {filename_v2} (Azure)...")
                    if generate_audio(text, lang, path_v2_abs, provider='azure'):
                        cursor.execute('''
                            INSERT INTO feedback (id, text, file_path, language, category, min_score, max_score)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (filename_v2.replace('.ogg',''), text, path_v2_rel, lang, 'common', min_s, max_s))
    
    conn.commit()
    conn.close()
    print("Done! All feedback audio generated and saved to DB.")

if __name__ == "__main__":
    main()