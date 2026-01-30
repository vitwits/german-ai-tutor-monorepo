import os
import re
import json
import random
from typing import Optional
from google import genai
from google.genai import types
from google.cloud import texttospeech
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Визначаємо корінь monorepo (на два рівні вище від app/services.py)
MONOREPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
load_dotenv(os.path.join(MONOREPO_ROOT, ".env"))

# Виправляємо шлях до credentials, якщо він відносний
creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if creds and not os.path.isabs(creds):
    # Якщо в .env просто "service-account.json", додаємо повний шлях
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(MONOREPO_ROOT, creds)

# Ініціалізація клієнта (New SDK)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

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
    # 1. Видаляємо Markdown обгортки
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    
    # 2. Шукаємо початок структури
    idx_brace = text.find('{')
    idx_bracket = text.find('[')
    
    # Якщо об'єкт починається раніше (або списку немає) -> це об'єкт
    if idx_brace != -1 and (idx_bracket == -1 or idx_brace < idx_bracket):
        last_brace = text.rfind('}')
        if last_brace != -1: return text[idx_brace:last_brace+1]

    # Якщо список починається раніше (або об'єкта немає) -> це список
    if idx_bracket != -1 and (idx_brace == -1 or idx_bracket < idx_brace):
        last_bracket = text.rfind(']')
        if last_bracket != -1: return text[idx_bracket:last_bracket+1]

    return text

# ============================================================================
# HELPER FUNCTIONS: Get AI preferences from database
# ============================================================================

async def get_llm_model_for_job(job_name: str, db: AsyncSession) -> str:
    """
    Отримує model_id LLM за назвою job з таблиці ai_preferences.
    Приклад: job='generate_texts' → 'gemini-2.5-flash-lite'
    
    Args:
        job_name: назва job ('generate_texts', 'generate_text_grammar')
        db: AsyncSession для запиту до БД
    
    Returns:
        model_id або fallback 'gemini-2.5-flash-lite'
    """
    try:
        from .models import AIPreference, LLMModel
        
        result = await db.execute(
            select(LLMModel.model_id).join(
                AIPreference, AIPreference.llm_model_id == LLMModel.id
            ).where(
                AIPreference.job == job_name,
                LLMModel.is_active == True
            )
        )
        model_id = result.scalar_one_or_none()
        return model_id or "gemini-2.5-flash-lite"
    except Exception as e:
        print(f"Error getting LLM model for {job_name}: {e}")
        return "gemini-2.5-flash-lite"

async def get_tts_voice_for_job(job_name: str, lang: str, db: AsyncSession) -> Optional[str]:
    """
    Отримує voice_name TTS за назвою job і мовою з таблиці ai_preferences.
    Приклад: job='generate_text_audio', lang='DE' → 'de-DE-Standard-B'
    
    Args:
        job_name: назва job ('generate_text_audio')
        lang: мова ('DE', 'EN', 'UA')
        db: AsyncSession для запиту до БД
    
    Returns:
        voice_name або None
    """
    try:
        from .models import AIPreference, TTSVoice
        
        result = await db.execute(
            select(TTSVoice.voice_name).join(
                AIPreference, AIPreference.tts_voice_id == TTSVoice.id
            ).where(
                AIPreference.job == job_name,
                TTSVoice.lang == lang,
                TTSVoice.is_active == True
            )
        )
        voice_name = result.scalar_one_or_none()
        return voice_name
    except Exception as e:
        print(f"Error getting TTS voice for {job_name}/{lang}: {e}")
        return None

# ============================================================================

async def generate_german_text(topic, count, level, style='neutral', db: AsyncSession = None):
    # Використовуємо змінну level. Якщо значення некоректне - фолбек на A2 (глобальний дефолт)
    if level not in CEFR_GUIDELINES:
        level = "A2"
    level_rules = CEFR_GUIDELINES[level]
    
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

    ADDITIONALLY GENERATE A QUIZ:
    - Create exactly 4 multiple-choice questions based on the text.
    - Language: German (questions and options).
    - Level: Same as text.
    - Format: 4 options per question, 1 correct answer. No duplicates.
    
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
      ],
      "quiz": [
          {{
              "question": "Question in German?",
              "options": ["Option A", "Option B", "Option C", "Option D"],
              "correct_index": 0  // Index of the correct option (0-3)
          }}
      ]
    }}"""
    
    try:
        # Get model_id from database if db is provided
        model_id = "gemini-2.5-flash-lite"  # Default fallback
        if db:
            model_id = await get_llm_model_for_job('generate_texts', db)
        
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7
            )
        )
        data = json.loads(clean_json_response(response.text))
        # Handle edge case where LLM returns a list instead of a dict
        if isinstance(data, list):
            data = data[0] if data else {}
        return data
    except Exception as e:
        print(f"Gen Error: {e}")
        return {"sentences": [], "title_ua": "Error", "title_de": "Error", "title_en": "Error"}

async def get_tts_audio(text, lang='de', db: AsyncSession = None):
    """
    Generates audio via Google TTS.
    
    Args:
        text: текст для озвучування
        lang: 'de' (German), 'uk' (Ukrainian), 'en' (English)
        db: AsyncSession для отримання голосу з БД (optional)
    """
    if not text: return None

    tts_client = get_tts_client()
    if not tts_client: return None

    # Спочатку намагаємся отримати voice з DB
    voice_name = None
    lang_code_map = {'de': 'DE', 'uk': 'UA', 'en': 'EN'}
    
    if db:
        tts_lang = lang_code_map.get(lang, 'DE')
        voice_name = await get_tts_voice_for_job('generate_text_audio', tts_lang, db)
    
    # Якщо не отримали з DB, користуємо fallback
    if not voice_name:
        if lang == 'de':
            voice_name = "de-DE-Standard-B"
        elif lang == 'uk':
            voice_name = "uk-UA-Standard-B"
        else:
            voice_name = "en-US-Standard-C"
    
    # Витягуємо language_code з voice_name (перші 5 символів: de-DE, uk-UA, en-US)
    language_code = voice_name[:5]

    s_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(language_code=language_code, name=voice_name)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.OGG_OPUS)
    
    try:
        response = tts_client.synthesize_speech(input=s_input, voice=voice, audio_config=audio_config)
        if not response or not response.audio_content:
            print(f"ERROR: TTS returned empty response for text='{text}', lang={lang}")
            return None
        return response.audio_content
    except Exception as e:
        print(f"ERROR in get_tts_audio: {str(e)} for text='{text}', lang={lang}")
        return None

def evaluate_audio_with_gemini(original_text, audio_bytes, interface_lang, mime_type='audio/webm'):
    """Оцінює аудіо-файл через Gemini. Відновлено гнучку логіку вчителя."""
    feedback_lang = "Ukrainian" if interface_lang == 'uk' else "English"
    
    prompt = f"""
    Role: Strict Goethe-Institut Examiner.
    Task: Evaluate the user's spoken German.
    
    REFERENCE GERMAN SENTENCE: "{original_text}"
    
    AUDIO ANALYSIS RULES:
    1. **Transcription**: Transcribe EXACTLY what is heard in the audio.
       - If the audio contains coughing, tapping, silence, or non-speech sounds -> Output "[NOISE]" and set ALL scores to 1.
       - If the user speaks a different language -> Set scores to 1.
       - **CRITICAL**: Do NOT hallucinate the Reference Sentence if it is not present in the audio. If the audio is unclear, transcribe what you hear (e.g., "mumble", "noise"), do not guess the sentence.
    
    2. **Scoring** (1-100):
       - Be highly critical. 100 is for native-level perfection only.
       - **Pronunciation**: Deduct heavily for strong accents or unclear phonemes.
       - **Context/Accuracy**: Compare the spoken text to the REFERENCE sentence. 
         * ACCEPT valid synonyms (e.g. 'günstig' instead of 'billig/niedrig'), alternative word orders, or phrasing IF the meaning remains correct and natural.
         * Do NOT penalize if the user uses a different but correct way to express the same idea.
         * Deduct points only if the meaning is changed, wrong, or words are missing.
       - **Grammar**: Deduct for wrong articles, endings, or structure.
       - If the user says nothing relevant -> Score 1.
    
    Output JSON ONLY:
    {{
        "transcribed_text": "Verbatim transcription or [NOISE]",
        "pronunciation_score": 1-100 (integer),
        "context_score": 1-100 (integer),
        "grammar_score": 1-100 (integer),
        "correction": "Correct German version (if needed, else null)"
    }}
    """
    
    try:
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
                response_mime_type="application/json",
                temperature=0.0 
            )
        )
        data = json.loads(clean_json_response(response.text))
        # Handle edge case where LLM returns a list
        if isinstance(data, list):
            data = data[0] if data else {}
        return data
    except Exception as e:
        print(f"Audio Eval Error: {e}")
        # Визначаємо текст помилки залежно від мови інтерфейсу
        if interface_lang in ['ukr', 'uk']:
            err_msg = "Помилка оцінки"
        else:
            err_msg = "Evaluation error"
            
        return {
            "pronunciation_score": 0,
            "context_score": 0,
            "grammar_score": 0,
            "correction": None, 
            "transcribed_text": ""
        }

def translate_word(text, ctx):
    # ПОВНИЙ, ОРИГІНАЛЬНИЙ ПРОМПТ
    prompt = f"""Translate the German word or phrase: "{text}". Context: "{ctx}".
    The input "{text}" has {len(text.split())} words.

    STRICT GRAMMAR RULES (NO EXCEPTIONS):

    0. **PRIORITY ORDER**: First, determine if the input is a phrase (2+ words) or a single word (exactly 1 word). Then apply rules.
    1. COLLOQUIALISMS, SLANG, AND CONTRACTIONS (HIGHEST PRIORITY):
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
       - **Nouns**: MUST include the correct definite article (der, die, das) in nominative singular, followed by the plural form in brackets. Example: "das Haus (die Häuser)".
       - Pluraletantum: "Leute (Pl.)".
       - Singularetantum: "das Obst (-)".
       
    3. SINGLE WORDS - EVERYTHING ELSE (Verbs, Adjectives, Pronouns, Adverbs):
       - **STRICT RULE**: Provide ONLY the base/infinitive form.
       - **FORBIDDEN**: Do not include any declensions, comparative forms, or endings in brackets.
       - **EXAMPLES**: 
          - "mein" -> "mein" (NOT "mein (meine, meiner)")
          - "langsam" -> "langsam" (NOT "langsam (langsamer)")
          - "machen" -> "machen"


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
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        data = json.loads(clean_json_response(response.text))
        # Handle edge case where LLM returns a list
        if isinstance(data, list):
            data = data[0] if data else {}
        return data
    except Exception as e:
        print(f"Translate Error: {e}")
        return {"display": text, "ua": "Error", "en": "Error", "level": "?"}

def explain_grammar_text(prompt_text, db: AsyncSession = None):
    """
    Виконує запит на пояснення граматики.
    
    Args:
        prompt_text: сформульований промпт
        db: AsyncSession для отримання моделі з БД (optional)
    """
    try:
        # NOTE: This is a sync function but needs async DB access
        # For now, use fallback model. Should be refactored to async in future
        model_id = "gemini-2.5-flash-lite"  # Default fallback
        
        response = client.models.generate_content(
            model=model_id,
            contents=prompt_text
        )
        return response.text
    except Exception as e:
        print(f"Grammar Error: {e}")
        return None