import os
import re
import json
from google import genai
from google.cloud import texttospeech
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Визначаємо чіткі інструкції для кожного рівня
CEFR_GUIDELINES = {
    "A1": "Use strictly short sentences (5-8 words). Structure: Subject-Verb-Object. Present tense only. Basic vocabulary (family, food, daily life). No complex subordinate clauses.",
    "A2": "Sentences 6-10 words. Use simple connectors (und, aber, oder). Use Perfekt for past tense. Topics: shopping, work, immediate environment.",
    "B1": "Sentences 8-15 words. MUST use subordinate clauses (weil, wenn, dass). Use Präteritum for modals. Introduce simple abstract topics. Start using distinct connecting words.",
    "B2": "Complex sentences (12-18+ words). MANDATORY use of: Passive voice, Konjunktiv II (speculation/politeness), relative clauses, and multi-part connectors (zwar... aber, nicht nur... sondern auch). Try to use at least one idiom useful for the context. Vocabulary must include abstract terms and specific synonyms. No simple repetition.",
    "C1": "Sophisticated structure (15-20 words). Use nominalization, complex syntax, fixed idiomatic expressions, and nuances. Text must flow logically with high cohesion. Advanced vocabulary is required.",
    "C2": "Mastery level. Long, nuanced sentences (18+ words). Use rhetorical devices, irony, and implicit meanings. Vocabulary must be highly specific, academic, or literary depending on context."
}

def get_tts_client():
    if os.path.exists(os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")):
        return texttospeech.TextToSpeechClient()
    return None

def clean_json_response(text):
    match = re.search(r'\{.*\}', text, re.DOTALL)
    return match.group(0) if match else text

def generate_german_text(topic, count, level):
    # Отримуємо специфічні правила для обраного рівня або дефолтні для B1
    level_rules = CEFR_GUIDELINES.get(level, CEFR_GUIDELINES["B1"])
    
    prompt = f"""You are an expert German linguist and teacher. 
    Generate a high-quality, coherent German text about "{topic}".
    
    TARGET LEVEL: {level} (Strictly adhere to CEFR standards).
    LENGTH: Exactly {count} sentences.
    
    LINGUISTIC REQUIREMENTS FOR {level}:
    {level_rules}
    
    INSTRUCTIONS:
    1. The text must make sense as a story or logical explanation, not just random sentences.
    2. Translate each sentence into Ukrainian (ua) and English (en).
    3. "de" field must contain ONLY natural German text. 
       - NO brackets with translations.
       - NO grammatical hints inside the text.
    
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
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "temperature": 0.7  # Трохи зменшуємо креативність для кращого дотримання правил
        }
    )
    return json.loads(clean_json_response(response.text))

def translate_word(text, ctx):
    prompt = f"""Translate the German word or phrase: "{text}". Context: "{ctx}".
    STRICT VOCAB FORMAT RULES:
    - For Nouns: das Haus (die Häuser)
    - For Verbs: abhören (hört ab, hörte ab, abgehört)
    - For Adjectives: schön (schöner, am schönsten)
    
    Provide:
    1. 'display': The word with grammar forms (plural, conjugation) as shown above.
    2. 'ua': 1-2 main meanings in Ukrainian.
    3. 'en': 1-2 main meanings in English.
    
    Return ONLY JSON:
    {{
      "display": "das Wort (Formen)",
      "ua": "переклад",
      "en": "translation"
    }}"""
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config={'response_mime_type': 'application/json'}
    )
    return json.loads(clean_json_response(response.text))