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

def get_tts_client():
    if os.path.exists(os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")):
        return texttospeech.TextToSpeechClient()
    return None

def clean_json_response(text):
    """
    Extracts valid JSON from text, handling:
    1. Markdown code blocks (```json ... ```)
    2. Multiple JSON objects (returns first valid one)
    3. Extra text before/after JSON
    """
    import json
    
    # 1. Remove Markdown wrappers
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()
    
    # 2. Try to find and parse first valid JSON object/array
    idx_brace = text.find('{')
    idx_bracket = text.find('[')
    
    # If object starts first (or array doesn't exist) -> try parsing as object
    if idx_brace != -1 and (idx_bracket == -1 or idx_brace < idx_bracket):
        # Extract from first { onwards
        json_text = text[idx_brace:]
        
        # Try parsing with progressively shorter strings to find valid JSON
        for end_pos in range(len(json_text), 0, -1):
            candidate = json_text[:end_pos]
            try:
                json.loads(candidate)
                return candidate  # Found valid JSON!
            except json.JSONDecodeError:
                continue
        
        # Fallback: return from first { to last }
        last_brace = text.rfind('}')
        if last_brace != -1:
            return text[idx_brace:last_brace+1]

    # If array starts first (or object doesn't exist) -> try parsing as array
    if idx_bracket != -1 and (idx_brace == -1 or idx_bracket < idx_brace):
        json_text = text[idx_bracket:]
        
        # Try parsing with progressively shorter strings
        for end_pos in range(len(json_text), 0, -1):
            candidate = json_text[:end_pos]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue
        
        # Fallback: return from first [ to last ]
        last_bracket = text.rfind(']')
        if last_bracket != -1:
            return text[idx_bracket:last_bracket+1]

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
    if not db:
        return "gemini-2.5-flash-lite"
    
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
    """
    Generate German text with translations.
    
    Returns:
        Tuple of (data_dict, prompt_text, raw_response_text, model_id)
        Where data_dict contains: title_de, title_ua, title_en, sentences, quiz
    """
    from .models import ModelPrompt
    result = await db.execute(
        select(ModelPrompt.prompt).where(
            ModelPrompt.name == "texts_cefr_guidelines"
        )
    )
    cefr_json = result.scalar_one_or_none()
    cefr_guidelines = {}
    if cefr_json:
        try:
            cefr_guidelines = json.loads(cefr_json)
        except Exception as e:
            print(f"Error parsing cefr_guidelines: {e}")
    
    # Отримуємо правила для рівня, або пустий string якщо рівня немає
    level_rules = cefr_guidelines.get(level, "")
    
    # Завантажуємо інструкцію для стилю з БД
    style_key = f"texts_style_{style}"
    result_style = await db.execute(
        select(ModelPrompt.prompt).where(
            ModelPrompt.name == style_key
        )
    )
    style_instruction = result_style.scalar_one_or_none() or ""
    if not style_instruction:
        print(f"⚠️ Style '{style_key}' not found in DB, using empty string")
    
    # Завантажуємо шаблон промпту з БД
    result_prompt = await db.execute(
        select(ModelPrompt.prompt).where(
            ModelPrompt.name == "texts_generation_prompt"
        )
    )
    prompt_template = result_prompt.scalar_one_or_none() or ""
    
    # Замінюємо placeholders у промпті
    prompt = (prompt_template
        .replace("{topic}", topic)
        .replace("{level}", level)
        .replace("{count}", str(count))
        .replace("{style_instruction}", style_instruction)
        .replace("{level_rules}", level_rules)
    )
    
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
        
        raw_response_text = response.text
        
        # 🔍 DEBUG: Print full raw response as received from API
        print("\n" + "="*80)
        print("🔍 DEBUG: FULL RAW RESPONSE FROM GEMINI API")
        print("="*80)
        print(raw_response_text)
        print("="*80 + "\n")
        
        data = json.loads(clean_json_response(raw_response_text))
        # Handle edge case where LLM returns a list instead of a dict
        if isinstance(data, list):
            data = data[0] if data else {}
        
        # Return tuple: (data, prompt, raw_response, model_id)
        return (data, prompt, raw_response_text, model_id)
    except Exception as e:
        print(f"Gen Error: {e}")
        error_data = {"sentences": [], "title_ua": "Error", "title_de": "Error", "title_en": "Error"}
        return (error_data, "", "", "gemini-2.5-flash-lite")

async def get_tts_audio(text, lang='de', db: AsyncSession = None, job_name='generate_text_audio'):
    """
    Generates audio via Google TTS.
    
    Args:
        text: текст для озвучування
        lang: 'de' (German), 'uk' (Ukrainian), 'en' (English)
        db: AsyncSession для отримання голосу з БД (optional)
        job_name: ім'я job у ai_preferences для отримання голосу (default: 'generate_text_audio')
                  Для vocabulary: 'vocabulary_tts_de', 'vocabulary_tts_ua', 'vocabulary_tts_en'
    """
    if not text: return None

    tts_client = get_tts_client()
    if not tts_client: return None

    # Спочатку намагаємся отримати voice з DB
    voice_name = None
    lang_code_map = {'de': 'DE', 'uk': 'UA', 'en': 'EN'}
    
    if db:
        tts_lang = lang_code_map.get(lang, 'DE')
        voice_name = await get_tts_voice_for_job(job_name, tts_lang, db)
    
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

async def evaluate_audio_with_gemini(original_text, audio_bytes, interface_lang, db: AsyncSession = None, mime_type='audio/webm'):
    """Оцінює аудіо-файл через Gemini. Завантажує модель і prompt з БД."""
    feedback_lang = "Ukrainian" if interface_lang == 'uk' else "English"
    
    # Отримуємо модель з ai_preferences за job 'speaking_feedback'
    llm_model_name = await get_llm_model_for_job("speaking_feedback", db)
    
    # Завантажуємо prompt з БД
    from .models import ModelPrompt
    result = await db.execute(
        select(ModelPrompt.prompt).where(
            ModelPrompt.name == "speaking_feedback_prompt"
        )
    )
    prompt_template = result.scalar_one_or_none() or ""
    # Замінюємо {original_text} без format() щоб не конфліктувати з JSON дужками
    prompt = prompt_template.replace("{original_text}", original_text)
    
    try:
        response = client.models.generate_content(
            model=llm_model_name,
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

async def translate_word(text, ctx, db: AsyncSession = None):
    # Отримуємо модель з DB або використовуємо fallback
    model_id = await get_llm_model_for_job('translate_vocabulary', db)
    
    # Завантажуємо prompt з БД
    from .models import ModelPrompt
    result = await db.execute(
        select(ModelPrompt.prompt).where(
            ModelPrompt.name == "translate_vocabulary_prompt"
        )
    )
    prompt_template = result.scalar_one_or_none() or ""
    # Замінюємо placeholders
    prompt = prompt_template.replace("{text}", text).replace("{ctx}", ctx).replace("{word_count}", str(len(text.split())))
    
    # DEBUG: Log input to LLM
    print(f"\n{'='*80}")
    print(f"📤 LLM INPUT TO translate_word:")
    print(f"{'='*80}")
    print(f"   model_id: {model_id}")
    print(f"   text: '{text}'")
    print(f"   ctx: '{ctx[:100]}...'")
    print(f"\n   📝 FULL PROMPT TO GEMINI:")
    print(f"   chars: {len(prompt)}")
    print(f"   content:\n{prompt}\n")
    
    try:
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        # DEBUG: Log output from LLM
        print(f"\n{'='*80}")
        print(f"📥 LLM OUTPUT FROM translate_word:")
        print(f"{'='*80}")
        print(f"   raw response chars: {len(response.text)}")
        print(f"   raw response:\n{response.text}\n")
        
        data = json.loads(clean_json_response(response.text))
        # Handle edge case where LLM returns a list
        if isinstance(data, list):
            data = data[0] if data else {}
        
        print(f"   parsed JSON:\n{json.dumps(data, ensure_ascii=False, indent=2)}\n")
        
        # Store full prompt and response for cost calculation
        data["_full_prompt"] = prompt
        data["_full_response"] = response.text
        
        return data
    except Exception as e:
        print(f"Translate Error: {e}")
        return {"display": text, "ua": "Error", "en": "Error", "level": "?"}
