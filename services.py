import os
import re
import hashlib
import json
from google import genai
from google.cloud import texttospeech
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def get_tts_client():
    if os.path.exists(os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")):
        return texttospeech.TextToSpeechClient()
    return None

def clean_json_response(text):
    match = re.search(r'\{.*\}', text, re.DOTALL)
    return match.group(0) if match else text

def generate_german_text(topic, count, level):
    prompt = f"""You are a German teacher. Generate a coherent German text about "{topic}".
    Level: {level}. Exactly {count} sentences.
    Translate each sentence into Ukrainian (ua) and English (en).
    CRITICAL RULES FOR TEXT:
    - The "de" field must contain ONLY pure German sentences.
    - STRICTLY FORBIDDEN: Do not include articles, plural forms, or translations in parentheses within the "de" sentence.
    Return ONLY JSON:
    {{
      "title_de": "German Title", "title_ua": "Ukrainian Title", "title_en": "English Title",
      "sentences": [ {{"de": "Clean German sentence", "ua": "Ukrainian translation", "en": "English translation"}} ]
    }}"""
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )
    return json.loads(clean_json_response(response.text))

def translate_word(text, ctx):
    prompt = f"""Translate the German word or phrase: "{text}". Context: "{ctx}".
    STRICT VOCAB FORMAT RULES:
    - For Nouns: das Haus (die Häuser)
    - For Verbs: abhören (hört ab, hörте ab, abgehört)
    - For Adjectives: schön (schöner, am schönsten)
    Give 1 or 2 translation variants in ukrainian and english.
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