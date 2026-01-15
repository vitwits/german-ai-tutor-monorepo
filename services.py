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

def generate_german_text(topic, count, level, style='neutral'):
    # Отримуємо специфічні правила для обраного рівня або дефолтні для B1
    level_rules = CEFR_GUIDELINES.get(level, CEFR_GUIDELINES["B1"])
    
    # Визначаємо інструкцію для стилю
    style_instruction = ""
    if style == 'formal':
        style_instruction = "Tone: Formal, academic, or professional. Use complex sentence structures suitable for the level."
    elif style == 'conversational':
        style_instruction = "Tone: Natural, conversational, storytelling style. Use idioms if appropriate for the level."
    elif style == 'dialogue_informal':
        style_instruction = "Format: A dialogue between two people. Tone: Informal/Casual (use 'Du'). Short, natural replies."
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

    STRICT GRAMMAR RULES (NO EXCEPTIONS):
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

    Provide JSON:
    {{
      "display": "Correct German form (No brackets for 2+ words)",
      "ua": "Meanings in Ukrainian",
      "en": "Meanings in English",
      "level": "A1-C2"
    }}"""
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config={'response_mime_type': 'application/json'}
    )
    return json.loads(clean_json_response(response.text))