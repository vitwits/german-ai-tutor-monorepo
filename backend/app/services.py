import os
import re
import json
import random
import subprocess
from typing import Optional
from google import genai
from google.genai import types
from google.cloud import texttospeech
from dotenv import load_dotenv
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

def get_audio_duration_exact(audio_bytes: bytes, mime_type: str = 'audio/webm') -> float:
    """
    Get exact audio duration using ffprobe.
    
    Args:
        audio_bytes: Raw audio data
        mime_type: MIME type of audio
    
    Returns:
        Duration in seconds (float), or 0 if unable to determine
    """
    try:
        import tempfile
        
        # Write bytes to temporary file
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        
        try:
            # Use ffprobe to get exact duration
            result = subprocess.run(
                [
                    'ffprobe',
                    '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    tmp_path
                ],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    duration = float(result.stdout.strip())
                    print(f"   ⏱️  Duration (ffprobe exact): {duration:.3f}s")
                    return duration
                except ValueError:
                    print(f"   ⚠️  Could not parse ffprobe output: {result.stdout}")
                    return 0
            else:
                print(f"   ⚠️  ffprobe error: {result.stderr}")
                return 0
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except:
                    pass
    
    except Exception as e:
        print(f"   ⚠️  Error getting duration: {e}")
        return 0


def trim_audio_silence(audio_bytes: bytes, trim_seconds: float = 1.0, audio_duration_seconds: float = None, mime_type: str = 'audio/webm') -> bytes:
    """
    Trims trailing silence from audio using ffmpeg (preserves WebM metadata).
    Uses -ss and -to flags to trim without re-encoding (stream copy).
    
    Args:
        audio_bytes: Raw audio data in WebM format (Opus codec)
        trim_seconds: Duration to trim from the end (default: 1.0 seconds - SILENCE_AFTER_SPEECH timeout)
        audio_duration_seconds: Total audio duration (required to calculate end time)
        mime_type: MIME type of audio (default: 'audio/webm')
    
    Returns:
        Trimmed audio bytes or original audio if trimming fails
    """
    try:
        print(f"\n🔪 TRIMMING AUDIO WITH FFMPEG:")
        print(f"   Original size: {len(audio_bytes) / 1024:.1f} KB")
        print(f"   Trim duration: {trim_seconds} seconds")
        
        if not audio_duration_seconds or audio_duration_seconds <= 0:
            print(f"   ⚠️ Unknown duration, returning original audio")
            return audio_bytes
        
        # Calculate the end time (duration - trim_seconds)
        end_time = max(0, audio_duration_seconds - trim_seconds)
        print(f"   Duration: {audio_duration_seconds:.3f}s → keeping until {end_time:.3f}s")
        
        # Create temporary files
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp_input:
            tmp_input.write(audio_bytes)
            tmp_input_path = tmp_input.name
        
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp_output:
            tmp_output_path = tmp_output.name
        
        try:
            # Use ffmpeg to trim without re-encoding
            # -c copy: stream copy (no re-encoding, instant)
            # -to: cut to specified duration
            cmd = [
                'ffmpeg',
                '-i', tmp_input_path,
                '-to', f'{end_time:.3f}',
                '-c', 'copy',  # Stream copy - no re-encoding
                '-y',  # Overwrite output
                tmp_output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            
            if result.returncode != 0:
                print(f"   ⚠️ ffmpeg failed: {result.stderr.decode()}")
                return audio_bytes
            
            # Read the trimmed audio
            with open(tmp_output_path, 'rb') as f:
                trimmed_bytes = f.read()
            
            print(f"   Trimmed size: {len(trimmed_bytes) / 1024:.1f} KB")
            print(f"   Size reduction: {(1 - len(trimmed_bytes) / len(audio_bytes)) * 100:.1f}%")
            
            return trimmed_bytes
        
        finally:
            # Clean up temp files
            for path in [tmp_input_path, tmp_output_path]:
                if os.path.exists(path):
                    try:
                        os.unlink(path)
                    except:
                        pass
    
    except Exception as e:
        print(f"   ⚠️ Trimming failed: {e}")
        print(f"   Returning original audio")
        return audio_bytes

def save_audio_for_debug(audio_bytes: bytes, filename_prefix: str = "debug_audio", stop_type: str = None):
    """
    Saves audio to debug_audio folder in backend root for debugging purposes.
    
    Args:
        audio_bytes: Raw audio data
        filename_prefix: Prefix for the file name
        stop_type: 'auto' or 'manual' - affects filename prefix
    """
    try:
        from datetime import datetime
        
        # Construct debug folder path (backend root / debug_audio)
        backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # app -> backend
        debug_folder = os.path.join(backend_root, "debug_audio")
        
        # Create folder if it doesn't exist
        os.makedirs(debug_folder, exist_ok=True)
        
        # Create filename with timestamp and stop_type
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Add stop_type to prefix if provided
        if stop_type:
            final_prefix = f"{filename_prefix}_{stop_type}"
        else:
            final_prefix = filename_prefix
        
        filename = f"{final_prefix}_{timestamp}.webm"
        filepath = os.path.join(debug_folder, filename)
        
        # Write audio file
        with open(filepath, 'wb') as f:
            f.write(audio_bytes)
        
        print(f"\n💾 DEBUG: Audio saved to: {filepath}")
        print(f"   File size: {len(audio_bytes) / 1024:.1f} KB")
        
    except Exception as e:
        print(f"   ⚠️ Failed to save debug audio: {e}")

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
    Automatically wraps abbreviations with SSML tags for proper pronunciation.
    
    Args:
        text: текст для озвучування
        lang: 'de' (German), 'uk' (Ukrainian), 'en' (English)
        db: AsyncSession для отримання голосу з БД (optional)
        job_name: ім'я job у ai_preferences для отримання голосу (default: 'generate_text_audio')
                  Для vocabulary: 'vocabulary_tts_de', 'vocabulary_tts_ua', 'vocabulary_tts_en'
    """
    if not text: return None

    # Prepare text with SSML tags for abbreviations
    from .ssml_utils import prepare_text_for_tts
    text = prepare_text_for_tts(text, lang=lang)

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

    # Wrap text in SSML root element for proper SSML processing
    ssml_text = f'<speak>{text}</speak>'
    s_input = texttospeech.SynthesisInput(ssml=ssml_text)
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

async def evaluate_audio_with_gemini(original_text, audio_bytes, interface_lang, db: AsyncSession = None, mime_type='audio/webm', stop_type=None):
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
    
    # 🔪 TRIM TRAILING SILENCE if auto-stopped (silence timeout triggered)
    if stop_type == 'auto':
        print(f"\n   🔪 Auto-stop detected - trimming trailing silence (1.0 second)")
        print(f"   📦 BEFORE trim - audio_bytes size: {len(audio_bytes)} bytes ({len(audio_bytes)/1024:.1f} KB)")
        
        # Get exact duration BEFORE trimming
        duration_before = get_audio_duration_exact(audio_bytes, mime_type)
        if duration_before == 0:
            duration_before = len(audio_bytes) / 16000  # Fallback estimate
        print(f"   📊 Original duration: {duration_before:.3f}s")
        
        # Trim 1.0 second (silence detection SILENCE_AFTER_SPEECH timeout)
        trim_seconds_value = 1.0
        audio_bytes = trim_audio_silence(audio_bytes, trim_seconds=trim_seconds_value, audio_duration_seconds=duration_before, mime_type=mime_type)
        
        print(f"   📦 AFTER trim - audio_bytes size: {len(audio_bytes)} bytes ({len(audio_bytes)/1024:.1f} KB)")
        
        # After trimming, calculate the new duration
        audio_duration_seconds = max(0, duration_before - trim_seconds_value)
        print(f"   ✂️  Duration after trimming: {audio_duration_seconds:.3f}s (calculated: {duration_before:.3f}s - {trim_seconds_value}s)")
    else:
        print(f"\n   ℹ️  Stop type: {stop_type or 'unknown'} - no trimming applied")
        # Get exact duration for manual stop
        audio_duration_seconds = get_audio_duration_exact(audio_bytes, mime_type)
        if audio_duration_seconds == 0:
            audio_duration_seconds = len(audio_bytes) / 16000  # Fallback estimate
        print(f"   📊 Audio duration: {audio_duration_seconds:.3f}s")
    
    # 💾 DEBUG: Save audio file for debugging
    save_audio_for_debug(audio_bytes, filename_prefix="debug_audio", stop_type=stop_type)
    
    print(f"\n{'='*80}")
    print(f"📤 LLM INPUT TO evaluate_audio_with_gemini:")
    print(f"{'='*80}")
    print(f"   model: {llm_model_name}")
    print(f"   interface_lang: {interface_lang}")
    print(f"   mime_type: {mime_type}")
    print(f"   stop_type: {stop_type or 'unknown'}")
    print(f"\n   📝 TEXT PROMPT:")
    print(f"      chars: {len(prompt)}")
    print(f"      content:\n{prompt}\n")
    print(f"\n   🔊 AUDIO INPUT:")
    print(f"      bytes: {len(audio_bytes)}")
    print(f"      duration: {audio_duration_seconds:.3f} seconds")
    print(f"      (about to send to Gemini...)")
    
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
        
        # DEBUG: Log output
        print(f"\n{'='*80}")
        print(f"📥 LLM OUTPUT FROM evaluate_audio_with_gemini:")
        print(f"{'='*80}")
        print(f"   raw response chars: {len(response.text)}")
        print(f"   raw response:\n{response.text}\n")
        
        data = json.loads(clean_json_response(response.text))
        # Handle edge case where LLM returns a list
        if isinstance(data, list):
            data = data[0] if data else {}
        
        # DEBUG: Log parsed output
        print(f"   parsed JSON:\n{json.dumps(data, ensure_ascii=False, indent=2)}\n")
        
        # Store full prompt and response for cost calculation
        data["_full_prompt"] = prompt
        data["_full_response"] = response.text
        data["_audio_bytes"] = len(audio_bytes)
        data["_audio_duration_seconds"] = audio_duration_seconds
        
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

async def translate_word(text, ctx, db: AsyncSession = None, user_id: str = None):
    """
    Translate word to 3 languages with retry logic.
    Attempts up to 3 times with 1 second delay between retries.
    Calculates and records cost of translation.
    """
    import asyncio
    
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
    print(f"   user_id: {user_id}")
    print(f"   text: '{text}'")
    print(f"   ctx: '{ctx[:100]}...'")
    print(f"\n   📝 FULL PROMPT TO GEMINI:")
    print(f"   chars: {len(prompt)}")
    print(f"   content:\n{prompt}\n")
    
    # Retry logic: 3 attempts with 1 second delay
    max_retries = 3
    for attempt in range(1, max_retries + 1):
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
            print(f"📥 LLM OUTPUT FROM translate_word (attempt {attempt}/{max_retries}):")
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
            
            # ============================================
            # COST CALCULATION & RECORDING
            # ============================================
            if user_id and db:
                print(f"\n📊 RECORDING COST FOR translate_word")
                print(f"{'='*80}")
                
                # Get user's interface language for cost calculation
                from .models import User
                user_result = await db.execute(select(User).where(User.id == user_id))
                user = user_result.scalar_one_or_none()
                interface_language = user.interface_language if user else 'en'
                
                # Call record_quick_translate_cost with full word data
                from . import cost_calculation
                cost_result = await cost_calculation.record_quick_translate_cost(
                    user_id, 
                    data, 
                    interface_language=interface_language,
                    db=db
                )
                
                print(f"✅ Cost recorded: {cost_result}")
                
                # Store cost info in response for debugging
                data["_cost_info"] = cost_result
            else:
                print(f"\n⚠️ COST NOT RECORDED (user_id={user_id}, db={bool(db)})")
            
            return data
        except Exception as e:
            print(f"Translate Error (attempt {attempt}/{max_retries}): {e}")
            
            # If it's the last attempt, return error
            if attempt == max_retries:
                print(f"❌ All {max_retries} attempts failed. Returning error response.")
                return {"display": text, "ua": "Error", "en": "Error", "level": "?"}
            
            # Wait 1 second before retrying
            print(f"⏳ Waiting 1 second before retry...")
            await asyncio.sleep(1)


async def translate_custom_word_async(text: str, user_id: str = None, db: AsyncSession = None):
    """
    Translate custom word/phrase without lesson context.
    Validates that input is German, and returns example sentence.
    Used for user-added custom vocabulary.
    Calculates and records cost of translation.
    """
    import asyncio
    
    # Get model from DB or use default
    model_id = 'gemini-2.0-flash' if not db else await get_llm_model_for_job('translate_custom_vocab', db)
    
    # Load prompt from DB
    prompt_template = None
    if db:
        from .models import ModelPrompt
        result = await db.execute(
            select(ModelPrompt.prompt).where(
                ModelPrompt.name == "add_custom_vocab"
            )
        )
        prompt_template = result.scalar_one_or_none()
    
    # Fallback prompt if not in DB
    if not prompt_template:
        prompt_template = """Translate the German word or phrase: "{text}". Context: "{ctx}".  
The input "{text}" has {word_count} words.  

STRICT GRAMMAR RULES (NO EXCEPTIONS):  
0. PRIORITY ORDER: First determine if input is phrase (2+ words) or single word (exactly 1 word). Then apply rules.  

1. COLLOQUIALISMS, SLANG, CONTRACTIONS (HIGHEST PRIORITY):  
   - If input is spoken contraction ("hast'e", "hab's", "bist'e", "gib's", "mach's") or slang ("nix", "ne"):  
   - YOU MUST PRESERVE colloquial spelling in 'display' field.  
   - DO NOT expand to standard German ("hast'e" ≠ "hast du").  
   - Format: "colloquial_form (standard_form)".  
   - Examples: "hast'e" → "hast'e (hast du)", "hab's" → "hab's (habe es)", "nix" → "nix (nichts)".  

2. PHRASES (2+ words):  
   - Convert to Nominative Singular: "die kontinuierliche Innovation".  
   - NEVER use brackets "()" or dashes "(-)" for phrases.  
   - Result MUST be clean text only.  
   - NO "die kontinuierliche Innovation (die kontinuierlichen Innovationen)" — ONLY "die kontinuierliche Innovation".  

3. SINGLE WORDS — Nouns:  
   - MUST include correct definite article (der/die/das) in nominative singular + plural in brackets.  
   - Example: "das Haus (die Häuser)".  
   - Pluraletantum: "Leute (Pl.)".  
   - Singularetantum: "das Obst (-)".  

4. SINGLE WORDS — Verbs, Adjectives, Pronouns, Adverbs etc.:  
   - Provide ONLY base/infinitive form.  
   - FORBIDDEN: declensions, comparatives, endings in brackets.  
   - Examples: "mein" → "mein", "langsam" → "langsam", "machen" → "machen".  

5. TRANSLATIONS: 1–2 main meanings. Clean text only.  

6. CEFR LEVEL (CRITICAL):  
   - Output EXACTLY ONE of: "A1", "A2", "B1", "B2", "C1", "C2".  
   - NEVER ranges ("A1-C2").  
   - Examples: "Haus" → "A1", "Argument" → "B1".  

7. VALIDATION:
   - Check if input is valid German (word or phrase)
   - If NOT German or invalid, return: {{"valid": false, "error": "Invalid German word or phrase"}}

IF VALID GERMAN:
Return ONLY minified JSON on a single line:
{{"display":"Correct German form (No brackets for 2+ words)","ua":"Meanings in Ukrainian","en":"Meanings in English","level":"A1-C2","context":"Example sentence in German only"}}"""
    
    prompt = prompt_template.replace("{text}", text).replace("{word_count}", str(len(text.split()))).replace("{ctx}", "")
    
    print(f"\n{'='*80}")
    print(f"📤 LLM INPUT TO translate_custom_word_async:")
    print(f"{'='*80}")
    print(f"   model_id: {model_id}")
    print(f"   user_id: {user_id}")
    print(f"   text: '{text}'")
    print(f"\n   📝 FULL PROMPT:")
    print(f"   {prompt}\n")
    
    # Retry logic: 3 attempts
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            print(f"\n{'='*80}")
            print(f"📥 LLM OUTPUT (attempt {attempt}/{max_retries}):")
            print(f"{'='*80}")
            print(f"   raw response:\n{response.text}\n")
            
            data = json.loads(clean_json_response(response.text))
            if isinstance(data, list):
                data = data[0] if data else {}
            
            # Check if validation failed
            if data.get("valid") == False:
                return {"success": False, "error": data.get("error", "Invalid word or phrase")}
            
            # Store full prompt and response for cost calculation
            data["_full_prompt"] = prompt
            data["_full_response"] = response.text
            
            # ============================================
            # COST CALCULATION & RECORDING
            # ============================================
            if user_id and db:
                print(f"\n📊 RECORDING COST FOR translate_custom_word_async")
                print(f"{'='*80}")
                
                # Get user's interface language for cost calculation
                from .models import User
                user_result = await db.execute(select(User).where(User.id == user_id))
                user = user_result.scalar_one_or_none()
                interface_language = user.interface_language if user else 'en'
                
                # Call record_quick_translate_cost with full word data
                from . import cost_calculation
                cost_result = await cost_calculation.record_quick_translate_cost(
                    user_id, 
                    data, 
                    interface_language=interface_language,
                    db=db
                )
                
                print(f"✅ Cost recorded: {cost_result}")
                
                # Store cost info in response for debugging
                data["_cost_info"] = cost_result
            else:
                print(f"\n⚠️ COST NOT RECORDED (user_id={user_id}, db={bool(db)})")
            
            # Success - validation passed
            return {
                "success": True,
                "display": data.get("display", text),
                "ua": data.get("ua", ""),
                "en": data.get("en", ""),
                "level": data.get("level", "A1"),
                "context": data.get("context", ""),
                "llm_cost": data.get("_cost_info", {}).get("llm_cost", 0.0)
            }
            
        except Exception as e:
            print(f"Error (attempt {attempt}/{max_retries}): {e}")
            if attempt == max_retries:
                return {"success": False, "error": "Failed to process word"}
            await asyncio.sleep(1)
    
    return {"success": False, "error": "All attempts failed"}


# ======================== BILLING ENERGY MANAGEMENT ========================

async def deduct_user_energy(
    db: AsyncSession,
    user_id: str,
    spending_usd: float
) -> dict:
    """
    Deduct energy from user's account based on USD spending
    
    Args:
        db: Database session
        user_id: User ID
        spending_usd: Amount spent in USD
    
    Returns:
        Dictionary with result and remaining energy
    """
    from .models import UserBilling, BillingPlan
    from .billing_logic import billing_manager, billing_init
    
    try:
        # Get billing plan
        plan_result = await db.execute(select(BillingPlan))
        billing_plan = plan_result.scalar_one_or_none()
        
        if not billing_plan:
            return {"ok": False, "error": "No billing plan configured"}
        
        # Get user billing
        billing_result = await db.execute(
            select(UserBilling).where(UserBilling.user_id == user_id)
        )
        user_billing = billing_result.scalar_one_or_none()
        
        # Auto-initialize billing if missing (for legacy users)
        if not user_billing:
            billing_data = billing_init.initialize_user_billing(
                user_id=user_id,
                monthly_credit_usd=billing_plan.monthly_credit,
                max_cap_days=billing_plan.max_cap_days
            )
            
            user_billing = UserBilling(
                user_id=billing_data['user_id'],
                subscription_status=billing_data['subscription_status'],
                billing_start_day=billing_data['billing_start_day'],
                billing_end_day=billing_data['billing_end_day'],
                energy_left=billing_data['energy_left'],
                daily_spending=billing_data['daily_spending'],
                price_per_point_usd=billing_data['price_per_point_usd'],
                last_energy_reset=billing_data['last_energy_reset'],
                last_billing_reset=billing_data['last_billing_reset']
            )
            db.add(user_billing)
            await db.flush()
        
        # Check if user can afford it
        if not billing_manager.can_spend_energy(user_billing, spending_usd):
            return {
                "ok": False,
                "error": "Insufficient energy",
                "energy_left": user_billing.energy_left,
                "energy_needed": spending_usd / user_billing.price_per_point_usd if user_billing.price_per_point_usd > 0 else 0
            }
        
        # Deduct energy
        updates = billing_manager.deduct_spending(
            user_billing,
            spending_usd,
            billing_plan.monthly_credit
        )
        
        # Apply updates
        for key, value in updates.items():
            setattr(user_billing, key, value)
        
        await db.commit()
        
        return {
            "ok": True,
            "energy_left": user_billing.energy_left,
            "daily_spending": user_billing.daily_spending,
            "subscription_status": user_billing.subscription_status
        }
    
    except Exception as e:
        await db.rollback()
        return {"ok": False, "error": str(e)}


async def get_user_energy_status(
    db: AsyncSession,
    user_id: str
) -> dict:
    """
    Get current energy status for user
    
    Args:
        db: Database session
        user_id: User ID
    
    Returns:
        Dictionary with energy status
    """
    from .models import UserBilling
    from .billing_logic import billing_calc
    
    try:
        billing_result = await db.execute(
            select(UserBilling).where(UserBilling.user_id == user_id)
        )
        user_billing = billing_result.scalar_one_or_none()
        
        if not user_billing:
            return {"error": "User billing not initialized"}
        
        status = billing_calc.get_energy_status(
            user_billing.energy_left,
            user_billing.daily_spending,
            user_billing.price_per_point_usd
        )
        
        return {
            "ok": True,
            "energy_status": status,
            "subscription_status": user_billing.subscription_status
        }
    
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def get_model_prompt(db: AsyncSession, prompt_name: str):
    """
    Get a model prompt by name from the database.
    
    Args:
        db: AsyncSession database connection
        prompt_name: Name of the prompt (e.g., "texts_create_own_text")
    
    Returns:
        ModelPrompt object or None if not found
    """
    from .models import ModelPrompt
    
    result = await db.execute(
        select(ModelPrompt).where(ModelPrompt.name == prompt_name)
    )
    return result.scalar_one_or_none()


async def create_lesson_from_user_text(text: str, prompt_template: str, db: AsyncSession):
    """
    Create lesson from user-provided German text using single LLM call.
    
    The texts_create_own_text prompt returns BOTH validation results AND lesson data
    in a single JSON response.
    
    Returns:
        Tuple: (validation_data, lesson_data, prompt_text, response_text, model_id)
        
        Where:
        - validation_data: dict with 6 validation fields + overall_validity
        - lesson_data: dict with title_de/ua/en, sentences, quiz, complexity_level_de
        - prompt_text: the actual prompt sent to LLM
        - response_text: the raw LLM response
        - model_id: the model used
    """
    from .models import AIPreference, LLMModel
    
    # Get LLM model for text generation (use existing pattern)
    model_id = await get_llm_model_for_job("generate_texts", db)
    
    # Format prompt with user text (level will be auto-detected by LLM)
    # Note: The prompt template expects text parameter, level will be determined by LLM analysis
    prompt = prompt_template.replace("{text}", text)
    
    # Call LLM once - temperature 0.3 for balanced validation and generation
    response = client.models.generate_content(
        model=model_id,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3,
            max_output_tokens=4000
        )
    )
    
    # Log token usage and cost
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        tokens_in = response.usage_metadata.prompt_token_count
        tokens_out = response.usage_metadata.total_token_count - tokens_in
        # Pricing for gemini-2.5-pro: $0.075/M input, $0.30/M output
        cost = (tokens_in * 0.075 + tokens_out * 0.30) / 1_000_000
        print(f"📊 LLM Cost: In={tokens_in} Out={tokens_out} Total={response.usage_metadata.total_token_count} | Cost=${cost:.6f}")
    
    # Parse response - contains both validation and lesson data
    try:
        if not response.text:
            raise ValueError("Empty response from LLM")
        response_data = json.loads(response.text)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        # Default fallback if JSON parsing fails
        print(f"⚠️ Error parsing response: {e}")
        response_data = {
            "validation_results": {
                "text_is_completely_in_german": False,
                "is_ethical": False,
                "no_sexual_content": False,
                "no_prohibited_topics": False,
                "is_safe_for_work": False,
                "overall_validity": False
            },
            "title_de": "Custom Lesson",
            "title_ua": "Користувацький урок",
            "title_en": "Custom Lesson",
            "complexity_level_de": "A1",
            "sentences": [{"de": text, "ua": text, "en": text}],
            "quiz": [],
            "vocabulary": []
        }
    
    # Extract validation results
    validation_data = response_data.get("validation_results", {})
    
    # Extract lesson data from response
    lesson_data = {
        "title_de": response_data.get("title_de", "Custom Lesson"),
        "title_ua": response_data.get("title_ua", "Користувацький урок"),
        "title_en": response_data.get("title_en", "Custom Lesson"),
        "complexity_level_de": response_data.get("complexity_level_de", "A1"),
        "sentences": response_data.get("sentences", []),
        "quiz": response_data.get("quiz", []),
        "vocabulary": response_data.get("vocabulary", [])
    }
    
    return validation_data, lesson_data, prompt, response.text, model_id
