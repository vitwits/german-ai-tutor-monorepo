import os
import re
import json
import random
from google import genai
from google.genai import types
from google.cloud import texttospeech
from dotenv import load_dotenv

load_dotenv()

# Ініціалізація клієнта (New SDK)
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# ПОВНІ ПРАВИЛА CEFR
CEFR_GUIDELINES = {
    "A1": "Use natural but simple sentences (5-9 words). Avoid 3-word sentences. Structure: Subject-Verb-Complement/Object. Present tense. Use common nouns and basic adjectives (e.g., instead of 'Das Kino ist klein', use 'Das kleine Kino ist sehr modern').",
    "A2": "Sentences 8-12 words. Avoid 6-word sentences. Use simple connectors (und, aber, oder). Use Perfekt for past tense. Topics: shopping, work, immediate environment.",
    "B1": "Sentences 10-15 words. MUST use subordinate clauses (weil, wenn, dass). Use Präteritum for modals. Introduce simple abstract topics. Start using distinct connecting words.",
    "B2": "Average length: 13-16 words. STRICT LIMIT: No sentence over 18 words and less than 13. Focus on syntactic variety: use Passive voice in one sentence, a Relative clause in another, and ONE multi-part connector (e.g., 'zwar... aber') in a third. DO NOT combine these in a single sentence. Include one idiom. Use abstract vocabulary, but keep the flow concise and teacher-like.",
    "C1": "Sophisticated structure (14-18 words). No sentence over 19 words and less than 13. Use nominalization, complex syntax, fixed idiomatic expressions, and nuances. Text must flow logically with high cohesion. Advanced vocabulary is required.",
    "C2": "Mastery level. Long, nuanced sentences (16-22 words). No sentence over 22 words and less than 15. Use rhetorical devices, irony, and implicit meanings. Vocabulary must be highly specific, academic, or literary depending on context."
}

def get_tts_client():
    if os.path.exists(os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")):
        return texttospeech.TextToSpeechClient()
    return None

def clean_json_response(text):
    # Покращена очистка: шукає [списки] або {об'єкти}
    match_list = re.search(r'\[.*\]', text, re.DOTALL)
    if match_list: return match_list.group(0)
    
    match_obj = re.search(r'\{.*\}', text, re.DOTALL)
    if match_obj: return match_obj.group(0)
    
    return text

def generate_german_text(topic, count, level, style='neutral'):
    # Отримуємо специфічні правила для обраного рівня або дефолтні для B1
    level_rules = CEFR_GUIDELINES.get(level, CEFR_GUIDELINES["B1"])
    
    # Визначаємо інструкцію для стилю (ПОВНА ВЕРСІЯ)
    style_instruction = ""
    if style == 'formal':
        style_instruction = "Tone: Formal, academic, or professional. Use complex sentence structures suitable for the level."
    elif style == 'conversational':
        style_instruction = """Tone: Authentic spoken German (Umgangssprache). 
        - Focus on how native speakers actually talk, not textbook German.
        - Use modal particles (e.g., 'halt', 'doch', 'mal', 'ja', 'eh') to make it sound natural.
        - Use common colloquial idioms and phrasing suitable for the level.
        - Avoid stiff or overly written constructions."""
    elif style == 'dialogue_informal':
        style_instruction = """Format: A realistic dialogue between close friends or family. 
        Tone: Highly Informal/Colloquial (Umgangssprache). 
        - MANDATORY use of 'Du'.
        - Use slang, conversational fillers, and interjections (e.g., 'Na?', 'Ach so', 'Echt jetzt?').
        - Use spoken contractions (e.g., 'mach's' instead of 'mache es', 'hast'e' instead of 'hast du' if appropriate).
        - Sentences should be dynamic, sometimes elliptical (incomplete), typical of real chats."""
    elif style == 'dialogue_formal':
        style_instruction = "Format: A dialogue between two people. Tone: Polite/Formal (use 'Sie'). Structured and courteous."
    else: # neutral
        style_instruction = "Tone: Neutral, descriptive, standard article style."

    prompt = f"""You are an expert German linguist and teacher. 
    Generate a high-quality, coherent German text about "{topic}".
    
    TARGET LEVEL: {level} (Strictly adhere to CEFR standards).
    LENGTH: Exactly {count} sentences.
    
    STYLE/TONE INSTRUCTIONS:
    {style_instruction}
    
    LINGUISTIC REQUIREMENTS FOR {level}:
    {level_rules}
    
    INSTRUCTIONS:
    1. The text must make sense as a story or logical explanation (or dialogue if specified), not just random sentences.
    2. Translate each sentence into Ukrainian (ua) and English (en).
    3. "de" field must contain ONLY natural German text. 
       - NO brackets with translations.
       - NO grammatical hints inside the text.
    !ABSOLUTE MAXIMUM: No sentence should ever exceed 22 words, even for C2!
    NO CLUTTER: Do not use multiple complex grammatical structures in a single sentence. Spread them across the text.
    NATURAL FLOW: The text must sound like it was written by a human teacher, not a grammar-obsessed robot.
    
    Return ONLY JSON:
    {{
      "title_de": "German Title ({level})", 
      "title_ua": "Ukrainian Title", 
      "title_en": "English Title",
      "sentences": [ 
          {{
              "de": "German sentence adhering to rules.", 
              "ua": "Ukrainian translation", 
              "en": "English translation"
          }} 
      ]
    }}"""
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7
            )
        )
        return json.loads(clean_json_response(response.text))
    except Exception as e:
        print(f"Gen Error: {e}")
        return {"sentences": [], "title_ua": "Error", "title_de": "Error", "title_en": "Error"}

def get_tts_audio(text, lang='de'):
    """
    Генерує аудіо через Google TTS.
    lang: 'de' (German), 'uk' (Ukrainian), 'en' (English)
    """
    if not text: return None
    tts_client = get_tts_client()
    if not tts_client: return None

    if lang == 'de':
        language_code = "de-DE"
        name = "de-DE-Polyglot-1" 
    elif lang == 'uk':
        language_code = "uk-UA"
        name = "uk-UA-Standard-A"
    else:
        language_code = "en-US"
        name = "en-US-Standard-H"

    s_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(language_code=language_code, name=name)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
    
    response = tts_client.synthesize_speech(input=s_input, voice=voice, audio_config=audio_config)
    return response.audio_content

def generate_practice_batch(count, level, interface_lang):
    """Генерує список речень для практики з випадковими темами"""
    
    topics_pool = [
        "Shopping & Groceries", "Travel by Train", "At the Restaurant", 
        "Job Interview", "Walking the Dog", "Cooking Dinner", 
        "Tech Support", "Planning a Holiday", "At the Doctor", 
        "Meeting Friends", "Hobbies & Sports", "Weather Forecast",
        "Public Transport", "Renting an Apartment", "Cinema & Movies"
    ]
    
    selected_topics = ", ".join(random.sample(topics_pool, 3))

    prompt = f"""Generate {count} unique, natural German sentences for a learner (Level {level}).
    Current Topics: {selected_topics}. Mix them.
    
    Output JSON ONLY (A list of objects):
    [
        {{
            "de": "German sentence",
            "source": "Translation in {interface_lang}"
        }}
    ]
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.9
            )
        )
        cleaned = clean_json_response(response.text)
        return json.loads(cleaned)
    except Exception as e:
        print(f"Batch Gen Error: {e}")
        return [{"de": "Hallo, wie geht es dir?", "source": "Привіт, як справи?"}]
    
def evaluate_audio_with_gemini(original_text, audio_bytes, interface_lang, mime_type='audio/webm'):
    """Оцінює аудіо-файл через Gemini"""
    feedback_lang = "Ukrainian" if interface_lang == 'uk' else "English"
    
    prompt = f"""
    You are a German teacher. Listen to the user's audio.
    Task: The user is trying to translate this sentence into German: "{original_text}".
    
    1. Transcribe EXACTLY what the user said in German.
    2. Compare it to the correct German translation of "{original_text}".
    3. Evaluate grammar, vocabulary, and pronunciation.
    4. If the audio is silent or unintelligible, set score to 0.
    
    Output JSON:
    {{
        "transcribed_text": "What user actually said",
        "score": 0-100 (integer),
        "feedback": "Short, encouraging phrase feedback in {feedback_lang} (max 3-5 words) or one word, don't use german language",
        "correction": "Correct German version"
    }}
    """
    
    try:
        # Використовуємо types.Blob для inline_data
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                prompt,
                types.Part(
                    inline_data=types.Blob(
                        mime_type=mime_type,
                        data=audio_bytes
                    )
                )
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        return json.loads(clean_json_response(response.text))
    except Exception as e:
        error_msg = str(e)
        print(f"Audio Eval Error: {error_msg}")
        return {
            "score": 0, 
            "feedback": f"Error: {error_msg[:50]}...", 
            "correction": None, 
            "transcribed_text": ""
        }

def translate_word(text, ctx):
    # ПОВНИЙ, ОРИГІНАЛЬНИЙ ПРОМПТ
    prompt = f"""Translate the German word or phrase: "{text}". Context: "{ctx}".

    STRICT GRAMMAR RULES (NO EXCEPTIONS):

    0. COLLOQUIALISMS, SLANG, AND CONTRACTIONS (HIGHEST PRIORITY):
       - IF the input is a spoken contraction (e.g., "hast'e", "hab's", "bist'e", "gib's", "mach's") or slang ("nix", "ne"):
       - **YOU MUST PRESERVE** the colloquial spelling in the 'display' field.
       - DO NOT expand it to standard German (e.g. DO NOT change "hast'e" to "hast du").
       - Format: "colloquial_form (standard_form)".
       - Examples: 
         * Input: "hast'e" -> Display: "hast'e (hast du)"
         * Input: "hab's" -> Display: "hab's (habe es)"
         * Input: "nix" -> Display: "nix (nichts)"

    1. PHRASES (2+ words):
       - If the input is a phrase (e.g., "kontinuierliche Innovationen", "ferne Sternensysteme"):
       - Convert to Nominative Singular: "die kontinuierliche Innovation".
       - NEVER use brackets "()" or dashes "(-)" for phrases. 
       - If there is more than one word, the result MUST be clean text only.
       - NO "die kontinuierliche Innovation (die kontinuierlichen Innovationen)" - ONLY "die kontinuierliche Innovation".

    2. SINGLE WORDS (Exactly 1 word):
       - Only if the input is a single word, provide forms in brackets.
       - Nouns: "das Haus (die Häuser)".
       - Pluraletantum: "Leute (Pl.)".
       - Singularetantum: "das Obst (-)".

    3. VERBS & ADJECTIVES (1 word):
       - Verbs: Infinitive only.
       - Adjectives: Base form (e.g., "stark").

    4. TRANSLATIONS:
       - 1-2 main meanings. Clean text only.

    5. CEFR LEVEL (CRITICAL):
       - Determine the specific CEFR level where this word/phrase is typically introduced.
       - OUTPUT MUST BE EXACTLY ONE OF: "A1", "A2", "B1", "B2", "C1", "C2".
       - NEVER return ranges like "A1-C2".
       - Example: "Haus" -> "A1", "Argument" -> "B1".

    Provide JSON:
    {{
      "display": "Correct German form (No brackets for 2+ words)",
      "ua": "Meanings in Ukrainian",
      "en": "Meanings in English",
      "level": "A1-C2"
    }}"""
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        return json.loads(clean_json_response(response.text))
    except Exception as e:
        print(f"Translate Error: {e}")
        return {"display": text, "ua": "Error", "en": "Error", "level": "?"}

def explain_grammar_text(prompt_text):
    """
    Виконує запит на пояснення граматики.
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt_text
        )
        return response.text
    except Exception as e:
        print(f"Grammar Error: {e}")
        return None