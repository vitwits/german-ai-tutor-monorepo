"""
Cost calculation module for tracking API usage and resource consumption.
Supports calculations for LLM models (tokens) and TTS models (characters).
"""

from typing import Literal

# Constants for LLM token calculation
# Characters to tokens ratio per language for text output
LANGUAGE_CHAR_TO_TOKEN_RATIO = {
    "en": 4.0,      # English: 4.0 characters = 1 token
    "de": 4.0,      # German: 4.0 characters = 1 token
    "uk": 2.8,      # Ukrainian: 2.8 characters = 1 token
}

# Audio input constant
AUDIO_TOKENS_PER_SECOND = 25  # 1 second of audio = 25 tokens


def calculate_audio_input_tokens(duration_seconds: float) -> int:
    """
    Calculate tokens consumed for audio input.
    
    Args:
        duration_seconds: Duration of audio in seconds
        
    Returns:
        Number of tokens consumed
    """
    return int(duration_seconds * AUDIO_TOKENS_PER_SECOND)


def calculate_text_output_tokens(text: str, language: str) -> float:
    """
    Calculate tokens consumed for text output based on language.
    
    Args:
        text: Output text
        language: Language code ('en', 'de', 'uk')
        
    Returns:
        Number of tokens consumed
        
    Raises:
        ValueError: If language is not supported
    """
    if language not in LANGUAGE_CHAR_TO_TOKEN_RATIO:
        raise ValueError(
            f"Unsupported language: {language}. "
            f"Supported: {list(LANGUAGE_CHAR_TO_TOKEN_RATIO.keys())}"
        )
    
    char_count = len(text)
    ratio = LANGUAGE_CHAR_TO_TOKEN_RATIO[language]
    
    # Characters / ratio = tokens
    tokens = char_count / ratio
    
    return tokens


def calculate_tts_characters(text: str) -> int:
    """
    Calculate characters consumed for TTS.
    Includes alphanumeric characters, punctuation, and white spaces.
    
    Args:
        text: Text to be synthesized
        
    Returns:
        Number of characters consumed
    """
    return len(text)


def calculate_llm_total_tokens(
    audio_duration_seconds: float = 0,
    text_output: str = "",
    language: str = "en"
) -> float:
    """
    Calculate total tokens for a complete LLM request.
    
    Args:
        audio_duration_seconds: Duration of audio input in seconds
        text_output: Generated text output
        language: Language of the text output
        
    Returns:
        Total tokens consumed
    """
    audio_tokens = calculate_audio_input_tokens(audio_duration_seconds)
    text_tokens = calculate_text_output_tokens(text_output, language) if text_output else 0
    
    return audio_tokens + text_tokens


def repair_json_response(json_text: str) -> str:
    """
    Repair common JSON syntax errors from Gemini API responses.
    
    Fixes:
    - Duplicate closing sequences and garbage at the end
    - Duplicate keys: "key":"value":"value" -> "key":"value"
    - Trailing commas before closing brackets
    - Multiple colons in succession
    
    Args:
        json_text: Potentially malformed JSON string
        
    Returns:
        Repaired JSON string
    """
    import re
    
    # AGGRESSIVE FIX: Find the FIRST valid }]} and remove everything after it
    # This handles cases where Gemini repeats garbage like:
    # }]}
    # index":1}]}
    # correct_index":1}]}
    # index":1}]}
    first_closing = json_text.rfind('"]}')  # Find last occurrence of "}]
    if first_closing > 0:
        # Find the actual first complete }]} (after the quiz closing)
        # Look for pattern: }]} that closes the main array
        pattern = r'(\}]\})'
        matches = list(re.finditer(pattern, json_text))
        if matches:
            # Keep only up to the first }]}
            first_match_end = matches[0].end()
            json_text = json_text[:first_match_end]
    
    # Fix: "key":"value":"value" -> "key":"value"
    json_text = re.sub(r'(":?")([^}{\[\]]*?)(":[\d]+")', r'\1\3', json_text)
    
    # Fix: "correct_index":2":2" or "correct_index":1":2 -> "correct_index":1
    # Pattern matches: "correct_index":<digit>":(<digit>) and keeps only first digit
    json_text = re.sub(r'"correct_index":(\d+)":\d+', r'"correct_index":\1', json_text)
    
    # Fix: trailing commas before ] or }
    json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
    
    # Fix: double colons :: -> :
    json_text = re.sub(r'::+', ':', json_text)
    
    return json_text


def is_error_response(status_code: int) -> bool:
    """
    Check if response status indicates an error that should not be charged.
    
    Args:
        status_code: HTTP status code
        
    Returns:
        True if error (400 or 500 range), False otherwise
    """
    return 400 <= status_code < 600

async def record_text_generation_cost(
    user_id: str,
    prompt_text: str,
    response_text: str,
    model_id: str,
    db=None
) -> dict:
    """
    Record cost for text generation with multilingual output.
    Splits output by language (DE, UA, EN) and calculates cost separately for each.
    
    Args:
        user_id: User ID to charge
        prompt_text: Input prompt text (all counted as English)
        response_text: Full JSON response with sentences and quiz in 3 languages
        model_id: Model ID used for generation (e.g., 'gemini-2.5-flash-lite')
        db: AsyncSession for database operations
        
    Returns:
        Dictionary with: {total_cost, llm_cost, tts_cost, error (if any)}
    """
    if not db or not response_text:
        return 0.0
    
    try:
        import json
        
        # DEBUG: Print received parameters
        print(f"\n🔍 DEBUG record_text_generation_cost:")
        print(f"   user_id: {user_id}")
        print(f"   model_id: {model_id}")
        print(f"   prompt_text length: {len(prompt_text)} chars")
        print(f"   response_text length: {len(response_text)} chars")
        print(f"\n   📝 FULL INPUT TEXT:\n{prompt_text}\n")
        print(f"   📝 FULL OUTPUT TEXT:\n{response_text}\n")
        
        # Step 1: Calculate input tokens (entire prompt as English)
        input_tokens = calculate_text_output_tokens(prompt_text, "en")
        
        # Step 2: Repair and parse JSON response
        repaired_response = repair_json_response(response_text)
        
        try:
            data = json.loads(repaired_response)
        except json.JSONDecodeError as e:
            print(f"⚠️ WARNING: Could not parse JSON even after repair: {e}")
            print(f"   Original: {response_text[:200]}...")
            print(f"   Repaired: {repaired_response[:200]}...")
            print(f"   Fallback: counting entire response as German\n")
            
            # Fallback: count entire response as German
            total_json_chars = len(response_text)
            de_chars = total_json_chars
            ua_chars = 0
            en_chars = 0
            
            ua_tokens = ua_chars / LANGUAGE_CHAR_TO_TOKEN_RATIO["uk"]
            en_tokens = en_chars / LANGUAGE_CHAR_TO_TOKEN_RATIO["en"]
            de_tokens = de_chars / LANGUAGE_CHAR_TO_TOKEN_RATIO["de"]
            total_output_tokens = ua_tokens + en_tokens + de_tokens
            
            data = None  # Skip structured extraction
        
        # Only extract if JSON parsing succeeded
        if data:
            # Extract content for each language (without spaces between elements)
            ua_title = data.get("title_ua", "")
            ua_sentences = "".join([sentence.get("ua", "") for sentence in data.get("sentences", [])])
            ua_content = ua_title + ua_sentences
            ua_chars = len(ua_content)
            
            en_title = data.get("title_en", "")
            en_sentences = "".join([sentence.get("en", "") for sentence in data.get("sentences", [])])
            en_content = en_title + en_sentences
            en_chars = len(en_content)
            
            # Total JSON length - UA and EN content = remainder (mostly German)
            total_json_chars = len(response_text)
            de_chars = total_json_chars - ua_chars - en_chars
            
            # DEBUG: Print character count breakdown
            print(f"🔍 DEBUG character count breakdown:")
            print(f"   input_text (EN): {len(prompt_text)} chars")
            print(f"   output_text (RAW JSON total): {total_json_chars} chars")
            print(f"      UA content: {ua_chars} chars")
            print(f"      EN content: {en_chars} chars")
            print(f"      DE (remainder): {de_chars} chars\n")
        
        # Step 3: Calculate output tokens for each language
        # Convert character counts to tokens using language-specific ratios
        ua_tokens = ua_chars / LANGUAGE_CHAR_TO_TOKEN_RATIO["uk"]
        en_tokens = en_chars / LANGUAGE_CHAR_TO_TOKEN_RATIO["en"]
        de_tokens = de_chars / LANGUAGE_CHAR_TO_TOKEN_RATIO["de"]
        total_output_tokens = ua_tokens + en_tokens + de_tokens
        
        print(f"🔍 DEBUG tokens calculated (by language ratio):")
        print(f"   input_tokens (EN): {input_tokens:.2f}")
        print(f"   output_tokens (UA): {ua_tokens:.2f} ({ua_chars} chars ÷ {LANGUAGE_CHAR_TO_TOKEN_RATIO['uk']})")
        print(f"   output_tokens (EN): {en_tokens:.2f} ({en_chars} chars ÷ {LANGUAGE_CHAR_TO_TOKEN_RATIO['en']})")
        print(f"   output_tokens (DE): {de_tokens:.2f} ({de_chars} chars ÷ {LANGUAGE_CHAR_TO_TOKEN_RATIO['de']})")
        print(f"   output_tokens (TOTAL): {total_output_tokens:.2f}\n")
        
        # Step 4: Get LLM model info from database
        from sqlalchemy import select
        from .models import LLMModel, LLMPrice
        
        model_result = await db.execute(
            select(LLMModel).where(LLMModel.model_id == model_id)
        )
        model = model_result.scalar_one_or_none()
        
        if not model:
            print(f"⚠️ Model not found: {model_id}")
            return 0.0
        
        # Step 5: Get prices for input and output
        input_price_result = await db.execute(
            select(LLMPrice).where(
                LLMPrice.llm_model_id == model.id,
                LLMPrice.direction == "input",
                LLMPrice.data_type == "text",
                LLMPrice.is_active == True
            )
        )
        input_price = input_price_result.scalar_one_or_none()
        
        output_price_result = await db.execute(
            select(LLMPrice).where(
                LLMPrice.llm_model_id == model.id,
                LLMPrice.direction == "output",
                LLMPrice.data_type == "text",
                LLMPrice.is_active == True
            )
        )
        output_price = output_price_result.scalar_one_or_none()
        
        if not input_price or not output_price:
            print(f"⚠️ Price not found for model: {model_id}")
            return 0.0
        
        # Step 6: Calculate costs
        input_cost = (input_tokens / 1_000_000) * input_price.price_per_unit
        ua_output_cost = (ua_tokens / 1_000_000) * output_price.price_per_unit
        en_output_cost = (en_tokens / 1_000_000) * output_price.price_per_unit
        de_output_cost = (de_tokens / 1_000_000) * output_price.price_per_unit
        total_output_cost = ua_output_cost + en_output_cost + de_output_cost
        total_cost = input_cost + total_output_cost
        
        print(f"🔍 DEBUG pricing found:")
        print(f"   input_price (per 1M tokens): ${input_price.price_per_unit}")
        print(f"   output_price (per 1M tokens): ${output_price.price_per_unit}")
        print(f"   input_cost: ${input_cost:.6f}")
        print(f"   output_cost (UA): ${ua_output_cost:.6f}")
        print(f"   output_cost (EN): ${en_output_cost:.6f}")
        print(f"   output_cost (DE): ${de_output_cost:.6f}")
        print(f"   total_output_cost: ${total_output_cost:.6f}")
        print(f"   total_cost: ${total_cost:.6f}\n")
        
        # Step 7: Update user's llm_cost
        from .models import User
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        
        if user:
            user.llm_cost = (user.llm_cost or 0.0) + total_cost
            user.total_cost = (user.total_cost or 0.0) + total_cost
            await db.commit()
            
            print(f"✅ Text generation cost recorded: ${total_cost:.6f} for user {user_id}")
            return {
                "total_cost": round(total_cost, 6),
                "llm_cost": round(total_cost, 6),
                "tts_cost": 0.0,
                "error": None
            }
        
        return {"total_cost": 0.0, "llm_cost": 0.0, "tts_cost": 0.0, "error": "User not found"}
        
    except Exception as e:
        print(f"❌ Error recording text generation cost: {e}")
        import traceback
        traceback.print_exc()
        return {"total_cost": 0.0, "llm_cost": 0.0, "tts_cost": 0.0, "error": str(e)}


async def record_tts_text_generation_cost(
    user_id: str,
    text: str,
    lang: str,
    job_name: str = "generate_text_audio",
    db=None
) -> float:
    """
    Record cost for TTS audio generation and update user's tts_cost.
    
    Args:
        user_id: User ID to charge
        text: Text to be converted to speech
        lang: Language code ('de', 'en', 'uk')
        job_name: Job name for AI preference lookup (default: 'generate_text_audio')
        db: AsyncSession for database operations
        
    Returns:
        Total cost calculated for TTS generation
    """
    if not db or not text:
        return 0.0
    
    try:
        # DEBUG: Print received parameters
        print(f"\n🔍 DEBUG record_tts_text_generation_cost:")
        print(f"   user_id: {user_id}")
        print(f"   lang: {lang}")
        print(f"   job_name: {job_name}")
        print(f"   text length: {len(text)} chars")
        print(f"   📝 FULL TEXT:\n{text}\n")
        
        # Step 1: Get TTS voice from AI preferences
        from sqlalchemy import select
        from .models import AIPreference, TTSVoice, TTSModel, User
        
        # Convert language code: 'uk' -> 'UA', 'de' -> 'DE', 'en' -> 'EN'
        lang_code_map = {'uk': 'UA', 'de': 'DE', 'en': 'EN'}
        db_lang = lang_code_map.get(lang.lower(), lang.upper())
        
        # Find TTS voice for this job and language
        voice_result = await db.execute(
            select(TTSVoice).join(
                AIPreference, AIPreference.tts_voice_id == TTSVoice.id
            ).where(
                AIPreference.job == job_name,
                TTSVoice.lang == db_lang,
                TTSVoice.is_active == True
            )
        )
        voice = voice_result.scalar_one_or_none()
        
        if not voice:
            print(f"⚠️ TTS voice not found for job={job_name}, lang={lang} (converted to {db_lang})")
            return 0.0
        
        print(f"🔍 DEBUG TTS voice found:")
        print(f"   voice_name: {voice.voice_name}")
        print(f"   tts_model_id: {voice.tts_model_id}")
        
        # Step 2: Get TTS model pricing
        model_result = await db.execute(
            select(TTSModel).where(TTSModel.id == voice.tts_model_id)
        )
        model = model_result.scalar_one_or_none()
        
        if not model:
            print(f"⚠️ TTS model not found for voice: {voice.voice_name}")
            return 0.0
        
        print(f"🔍 DEBUG TTS model found:")
        print(f"   human_name: {model.human_name}")
        print(f"   provider: {model.provider}")
        print(f"   price_per_1m_chars: ${model.price_per_unit}")
        
        # Step 3: Calculate cost based on input characters
        # TTS is charged per character (input only)
        # price_per_unit is price per 1M characters, convert to price per character
        char_count = len(text)
        price_per_char = model.price_per_unit / 1_000_000
        
        # Calculate cost: characters × price_per_character
        total_cost = char_count * price_per_char
        
        print(f"🔍 DEBUG TTS cost calculation:")
        print(f"   char_count: {char_count}")
        print(f"   price_per_char: ${price_per_char:.9f}")
        print(f"   total_cost: ${total_cost:.6f}\n")
        
        # Step 4: Update user's tts_cost
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        
        if user:
            user.tts_cost = (user.tts_cost or 0.0) + total_cost
            user.total_cost = (user.total_cost or 0.0) + total_cost
            await db.commit()
            
            print(f"✅ TTS generation cost recorded: ${total_cost:.6f} for user {user_id}")
            return total_cost
        
        return 0.0
        
    except Exception as e:
        print(f"❌ Error recording TTS generation cost: {e}")
        import traceback
        traceback.print_exc()
        return 0.0


async def record_quick_translate_cost(
    user_id: str,
    word_data: dict,
    interface_language: str = "en",
    db=None
) -> dict:
    """
    Record cost for quick_translate operation (word translation + TTS generation).
    
    Calculates:
    1. LLM cost: full prompt input → output (split by language: DE, UK, EN, JSON markup)
    2. TTS cost: display + translation parts (only for interface language)
    
    Writes to user: llm_cost, tts_cost, total_cost
    
    Args:
        user_id: User ID to charge
        word_data: Dict from translate_word() containing:
                   - display, ua, en, level (translation results)
                   - _full_prompt (entire prompt sent to LLM)
                   - _full_response (raw JSON response from LLM)
        interface_language: User's interface language ('en', 'ukr', etc.)
        db: AsyncSession for database operations
        
    Returns:
        Dict with: {llm_cost, tts_cost, total_cost, error (if any)}
    """
    if not db:
        return {"llm_cost": 0.0, "tts_cost": 0.0, "total_cost": 0.0, "error": "No database"}
    
    try:
        from sqlalchemy import select
        from .models import LLMModel, LLMPrice, TTSVoice, TTSModel, User, AIPreference
        
        # Extract data
        full_prompt = word_data.get("_full_prompt", "")
        full_response = word_data.get("_full_response", "")
        display_text = word_data.get("display", "")
        ua_text = word_data.get("ua", "")
        en_text = word_data.get("en", "")
        
        print(f"\n{'='*80}")
        print(f"🔍 DEBUG record_quick_translate_cost")
        print(f"{'='*80}")
        print(f"   user_id: {user_id}")
        print(f"\n   📝 FULL LLM EXCHANGE:")
        print(f"      INPUT prompt: {len(full_prompt)} chars")
        print(f"      OUTPUT response: {len(full_response)} chars")
        print(f"\n   📝 TRANSLATION RESULTS:")
        print(f"      display (DE): '{display_text}' ({len(display_text)} chars)")
        print(f"      ua (UK): '{ua_text}' ({len(ua_text)} chars)")
        print(f"      en (EN): '{en_text}' ({len(en_text)} chars)")
        
        # ============================================
        # PART 1: LLM COST CALCULATION
        # ============================================
        print(f"\n📊 PART 1: LLM COST CALCULATION")
        print(f"{'-'*80}")
        
        # Step 1.1: Get LLM model
        llm_model_result = await db.execute(
            select(LLMModel).join(
                AIPreference, AIPreference.llm_model_id == LLMModel.id
            ).where(
                AIPreference.job == "translate_vocabulary",
                LLMModel.is_active == True
            )
        )
        llm_model = llm_model_result.scalar_one_or_none()
        
        if not llm_model:
            print(f"⚠️ LLM model not found for job='translate_vocabulary'")
            return {"llm_cost": 0.0, "tts_cost": 0.0, "total_cost": 0.0, "error": "LLM model not found"}
        
        print(f"   LLM Model: {llm_model.human_name} (id={llm_model.model_id})")
        
        # Step 1.2: Get LLM prices (input + output)
        input_price_result = await db.execute(
            select(LLMPrice).where(
                LLMPrice.llm_model_id == llm_model.id,
                LLMPrice.direction == "input",
                LLMPrice.data_type == "text",
                LLMPrice.is_active == True
            )
        )
        input_price = input_price_result.scalar_one_or_none()
        
        output_price_result = await db.execute(
            select(LLMPrice).where(
                LLMPrice.llm_model_id == llm_model.id,
                LLMPrice.direction == "output",
                LLMPrice.data_type == "text",
                LLMPrice.is_active == True
            )
        )
        output_price = output_price_result.scalar_one_or_none()
        
        if not input_price or not output_price:
            print(f"⚠️ LLM prices not found for model {llm_model.model_id}")
            return {"llm_cost": 0.0, "tts_cost": 0.0, "total_cost": 0.0, "error": "LLM prices not found"}
        
        print(f"   Input price: ${input_price.price_per_unit}/млн tokens")
        print(f"   Output price: ${output_price.price_per_unit}/млн tokens")
        
        # Step 1.3: Calculate input tokens (FULL PROMPT as English)
        input_tokens = calculate_text_output_tokens(full_prompt, "en")
        print(f"\n   📝 INPUT TOKENS:")
        print(f"      full_prompt chars: {len(full_prompt)}")
        print(f"      tokens (en 4.0 ratio): {input_tokens:.2f}")
        
        # Step 1.4: Calculate output tokens (smart split by language)
        # display → DE, ua → UK, en → EN
        # Remainder (JSON markup) → EN
        display_tokens = calculate_text_output_tokens(display_text, "de")
        ua_tokens = calculate_text_output_tokens(ua_text, "uk")
        en_tokens = calculate_text_output_tokens(en_text, "en")
        
        # Calculate remainder (JSON markup + field names + etc)
        # remainder = full_response - display - ua - en
        remaining_chars = len(full_response) - len(display_text) - len(ua_text) - len(en_text)
        remaining_tokens = calculate_text_output_tokens("x" * remaining_chars, "en") if remaining_chars > 0 else 0
        
        total_output_tokens = display_tokens + ua_tokens + en_tokens + remaining_tokens
        
        print(f"\n   📝 OUTPUT TOKENS (split by language):")
        print(f"      display (DE): '{display_text}' ({len(display_text)} chars) → {display_tokens:.2f} tokens (4.0 ratio)")
        print(f"      ua (UK): '{ua_text}' ({len(ua_text)} chars) → {ua_tokens:.2f} tokens (2.8 ratio)")
        print(f"      en (EN): '{en_text}' ({len(en_text)} chars) → {en_tokens:.2f} tokens (4.0 ratio)")
        print(f"      JSON markup + rest: {remaining_chars} chars → {remaining_tokens:.2f} tokens (4.0 ratio)")
        print(f"      TOTAL: {total_output_tokens:.2f} tokens")
        
        # Step 1.5: Calculate LLM costs
        llm_input_cost = (input_tokens / 1_000_000) * input_price.price_per_unit
        llm_output_cost = (total_output_tokens / 1_000_000) * output_price.price_per_unit
        llm_total_cost = llm_input_cost + llm_output_cost
        
        print(f"\n   💰 LLM COSTS:")
        print(f"      input_cost: ({input_tokens:.2f} / 1M) × ${input_price.price_per_unit} = ${llm_input_cost:.6f}")
        print(f"      output_cost: ({total_output_tokens:.2f} / 1M) × ${output_price.price_per_unit} = ${llm_output_cost:.6f}")
        print(f"      llm_total_cost: ${llm_total_cost:.6f}")
        
        # ============================================
        # PART 2: TTS COST CALCULATION
        # ============================================
        print(f"\n📊 PART 2: TTS COST CALCULATION")
        print(f"{'-'*80}")
        
        # Determine target language for TTS
        target_lang = 'uk' if interface_language == 'ukr' else 'en'
        trans_text = word_data.get('ua') if target_lang == 'uk' else word_data.get('en')
        
        # Map language codes to job names
        # target_lang is 'uk' or 'en', but job names use 'ua' for Ukrainian
        job_lang_map = {'uk': 'ua', 'en': 'en'}
        job_lang = job_lang_map.get(target_lang, target_lang)
        
        print(f"   User's interface_language: {interface_language} → TTS target_lang: {target_lang.upper()}")
        
        tts_total_cost = 0.0
        
        # Get TTS voices and models for German + interface language only
        import re
        tts_items = [
            ("de", display_text, "display", "vocabulary_tts_de"),
            (target_lang, trans_text, "translation", f"vocabulary_tts_{job_lang}"),
        ]
        
        for lang_code, text, text_type, job_name in tts_items:
            if not text:
                print(f"   ⏭️  Skipping {text_type.upper()} - empty text")
                continue
            
            # Split by commas/semicolons just like in vocabulary.py
            # display is NOT split (single word), but translations are split
            if text_type == "display":
                parts = [text]  # German display word is not split
            else:
                # Split translations by comma/semicolon
                parts = [p.strip() for p in re.split(r'[,;]', text) if p.strip()]
            
            print(f"\n   🎤 {text_type.upper()} ({lang_code.upper()}):")
            print(f"      original text: '{text}'")
            print(f"      parts to TTS: {parts} ({len(parts)} part{'s' if len(parts) != 1 else ''})")
            
            # Get TTS voice for this job
            voice_result = await db.execute(
                select(TTSVoice).join(
                    AIPreference, AIPreference.tts_voice_id == TTSVoice.id
                ).where(
                    AIPreference.job == job_name,
                    TTSVoice.is_active == True
                )
            )
            voice = voice_result.scalar_one_or_none()
            
            if not voice:
                print(f"      ⚠️ TTS voice not found for job={job_name}")
                continue
            
            print(f"      voice: {voice.voice_name}")
            
            # Get TTS model
            model_result = await db.execute(
                select(TTSModel).where(TTSModel.id == voice.tts_model_id)
            )
            model = model_result.scalar_one_or_none()
            
            if not model:
                print(f"      ⚠️ TTS model not found")
                continue
            
            print(f"      model: {model.human_name} (${model.price_per_unit}/млн chars)")
            
            # Calculate TTS cost for each part
            price_per_char = model.price_per_unit / 1_000_000
            lang_cost = 0.0
            for part in parts:
                char_count = len(part)
                part_cost = char_count * price_per_char
                lang_cost += part_cost
                print(f"         • '{part}' ({char_count} chars) = ${part_cost:.6f}")
            
            tts_total_cost += lang_cost
            print(f"      total for {text_type.upper()}: ${lang_cost:.6f}")
        
        print(f"\n   💰 TTS TOTAL COST: ${tts_total_cost:.6f}")
        print(f"      ⚠️ NOTE: TTS cost already added to user.tts_cost by get_cached_or_generate_tts()")
        print(f"      This is calculated here for tracking/logging purposes only")
        
        # ============================================
        # PART 3: UPDATE USER IN DATABASE
        # ============================================
        print(f"\n📊 PART 3: UPDATE USER DATABASE")
        print(f"{'-'*80}")
        
        # IMPORTANT: Only add LLM cost here. TTS cost is already added by get_cached_or_generate_tts calls
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        
        if not user:
            print(f"⚠️ User not found: {user_id}")
            return {"llm_cost": 0.0, "tts_cost": 0.0, "total_cost": 0.0, "error": f"User not found"}
        
        # Update user costs - ONLY LLM, NOT TTS (TTS already added)
        user.llm_cost = (user.llm_cost or 0.0) + llm_total_cost
        # NOTE: Do NOT add tts_cost here - it's already added by get_cached_or_generate_tts
        user.total_cost = (user.total_cost or 0.0) + llm_total_cost  # Only add LLM to total
        await db.commit()
        
        print(f"   ✅ llm_cost added: ${llm_total_cost:.6f}")
        print(f"   ℹ️  tts_cost (not added here): ${tts_total_cost:.6f} [already recorded by get_cached_or_generate_tts]")
        print(f"   ✅ total_cost added: ${llm_total_cost:.6f} (LLM only)")
        print(f"   User {user_id} updated successfully")
        
        print(f"\n{'='*80}")
        print(f"✅ TOTAL IMPACT: ${llm_total_cost + tts_total_cost:.6f}")
        print(f"   - LLM added to DB: ${llm_total_cost:.6f}")
        print(f"   - TTS tracked: ${tts_total_cost:.6f} (already in DB from get_cached_or_generate_tts)")
        print(f"{'='*80}\n")
        
        return {
            "llm_cost": round(llm_total_cost, 6),
            "tts_cost": round(tts_total_cost, 6),
            "total_cost": round(llm_total_cost + tts_total_cost, 6),
            "error": None
        }
        
    except Exception as e:
        print(f"❌ Error recording quick_translate cost: {e}")
        import traceback
        traceback.print_exc()
        return {"llm_cost": 0.0, "tts_cost": 0.0, "total_cost": 0.0, "error": str(e)}


async def record_feedback_cost(
    user_id: str,
    feedback_data: dict,
    db=None
) -> dict:
    """
    Record cost for speaking feedback operation (audio evaluation).
    
    Calculates:
    1. Audio input tokens: duration_seconds × AUDIO_TOKENS_PER_SECOND
    2. Text input tokens: full prompt (counted as English)
    3. JSON output tokens: split by language (German transcribed_text + correction, rest is English)
    
    Writes to user: llm_cost, total_cost
    
    Args:
        user_id: User ID to charge
        feedback_data: Dict from evaluate_audio_with_gemini() containing:
                      - _full_prompt (entire text prompt)
                      - _full_response (raw JSON response)
                      - _audio_bytes (length of audio bytes)
                      - _audio_duration_seconds (estimated duration)
                      - transcribed_text (German transcription)
                      - correction (German correction, if any)
                      - pronunciation_score, context_score, grammar_score (scoring results)
        db: AsyncSession for database operations
        
    Returns:
        Dict with: {llm_cost, total_cost, error (if any)}
    """
    if not db:
        return {"llm_cost": 0.0, "total_cost": 0.0, "error": "No database"}
    
    try:
        from sqlalchemy import select
        from .models import LLMModel, LLMPrice, User, AIPreference
        
        # Extract data
        full_prompt = feedback_data.get("_full_prompt", "")
        full_response = feedback_data.get("_full_response", "")
        audio_bytes_len = feedback_data.get("_audio_bytes", 0)
        audio_duration_seconds = feedback_data.get("_audio_duration_seconds", 0.0)
        transcribed_text = feedback_data.get("transcribed_text", "")
        correction = feedback_data.get("correction") or ""  # Handle null/None by converting to empty string
        
        print(f"\n{'='*80}")
        print(f"🔍 DEBUG record_feedback_cost")
        print(f"{'='*80}")
        print(f"   user_id: {user_id}")
        
        print(f"\n   📝 FULL LLM EXCHANGE:")
        print(f"      INPUT prompt: {len(full_prompt)} chars")
        print(f"      INPUT audio: {audio_bytes_len} bytes (~{audio_duration_seconds:.2f} seconds)")
        print(f"      OUTPUT response: {len(full_response)} chars")
        
        print(f"\n   📝 RESPONSE CONTENT:")
        print(f"      transcribed_text (DE): '{transcribed_text}' ({len(transcribed_text)} chars)")
        print(f"      correction (DE): '{correction}' ({len(correction)} chars)")
        
        # ============================================
        # PART 1: INPUT TOKENS CALCULATION
        # ============================================
        print(f"\n📊 PART 1: INPUT TOKENS CALCULATION")
        print(f"{'-'*80}")
        
        # Step 1.1: Get LLM model
        llm_model_result = await db.execute(
            select(LLMModel).join(
                AIPreference, AIPreference.llm_model_id == LLMModel.id
            ).where(
                AIPreference.job == "speaking_feedback",
                LLMModel.is_active == True
            )
        )
        llm_model = llm_model_result.scalar_one_or_none()
        
        if not llm_model:
            print(f"⚠️ LLM model not found for job='speaking_feedback'")
            return {"llm_cost": 0.0, "total_cost": 0.0, "error": "LLM model not found"}
        
        print(f"   LLM Model: {llm_model.human_name} (id={llm_model.model_id})")
        
        # Step 1.2: Get LLM prices (input + output)
        # For feedback: we need combined input (text + audio), but pricing is usually unified
        # Get text input price first, then audio input price separately
        input_price_result = await db.execute(
            select(LLMPrice).where(
                LLMPrice.llm_model_id == llm_model.id,
                LLMPrice.direction == "input",
                LLMPrice.data_type == "text",  # Text input pricing
                LLMPrice.is_active == True
            )
        )
        input_price = input_price_result.scalar_one_or_none()
        
        # Get audio input price if available
        audio_input_price_result = await db.execute(
            select(LLMPrice).where(
                LLMPrice.llm_model_id == llm_model.id,
                LLMPrice.direction == "input",
                LLMPrice.data_type == "audio",  # Audio input pricing
                LLMPrice.is_active == True
            )
        )
        audio_input_price = audio_input_price_result.scalar_one_or_none()
        
        output_price_result = await db.execute(
            select(LLMPrice).where(
                LLMPrice.llm_model_id == llm_model.id,
                LLMPrice.direction == "output",
                LLMPrice.data_type == "text",  # Text output pricing
                LLMPrice.is_active == True
            )
        )
        output_price = output_price_result.scalar_one_or_none()
        
        if not input_price or not output_price:
            print(f"⚠️ LLM prices not found for model {llm_model.model_id}")
            return {"llm_cost": 0.0, "total_cost": 0.0, "error": "LLM prices not found"}
        
        # Use audio price if available, otherwise use text price for audio tokens
        effective_audio_input_price = audio_input_price if audio_input_price else input_price
        
        print(f"   Text input price: ${input_price.price_per_unit}/млн tokens")
        print(f"   Audio input price: ${effective_audio_input_price.price_per_unit}/млн tokens")
        print(f"   Output price: ${output_price.price_per_unit}/млн tokens")
        
        # Step 1.3: Calculate input tokens (text prompt as English + audio)
        text_input_tokens = calculate_text_output_tokens(full_prompt, "en")
        
        # Audio tokens: duration × 25 tokens/second (with decimal precision)
        audio_input_tokens = audio_duration_seconds * AUDIO_TOKENS_PER_SECOND
        
        total_input_tokens = text_input_tokens + audio_input_tokens
        
        print(f"\n   📝 INPUT TOKENS:")
        print(f"      text prompt: {len(full_prompt)} chars → {text_input_tokens:.2f} tokens (en 4.0 ratio)")
        print(f"      audio duration: {audio_duration_seconds:.2f} seconds → {audio_input_tokens:.2f} tokens (25 tokens/sec)")
        print(f"      TOTAL INPUT: {total_input_tokens:.2f} tokens")
        
        # ============================================
        # PART 2: OUTPUT TOKENS CALCULATION
        # ============================================
        print(f"\n📊 PART 2: OUTPUT TOKENS CALCULATION")
        print(f"{'-'*80}")
        
        # Step 2.1: Calculate German content (transcribed_text + correction)
        german_content = transcribed_text + correction
        german_chars = len(german_content)
        german_tokens = calculate_text_output_tokens(german_content, "de")
        
        # Step 2.2: Calculate English content (remainder of JSON)
        total_json_chars = len(full_response)
        english_chars = total_json_chars - german_chars
        english_tokens = calculate_text_output_tokens("x" * english_chars, "en") if english_chars > 0 else 0
        
        total_output_tokens = german_tokens + english_tokens
        
        print(f"\n   📝 OUTPUT TOKENS (split by language):")
        print(f"      german (transcribed + correction): {german_chars} chars → {german_tokens:.2f} tokens (4.0 ratio)")
        print(f"         transcribed_text: '{transcribed_text}' ({len(transcribed_text)} chars)")
        print(f"         correction: '{correction}' ({len(correction)} chars)")
        print(f"      english (JSON markup + rest): {english_chars} chars → {english_tokens:.2f} tokens (4.0 ratio)")
        print(f"      TOTAL OUTPUT: {total_output_tokens:.2f} tokens")
        
        # ============================================
        # PART 3: COST CALCULATION
        # ============================================
        print(f"\n📊 PART 3: COST CALCULATION")
        print(f"{'-'*80}")
        
        # Calculate input cost (text + audio with separate pricing)
        text_input_cost = (text_input_tokens / 1_000_000) * input_price.price_per_unit
        audio_input_cost = (audio_input_tokens / 1_000_000) * effective_audio_input_price.price_per_unit
        total_input_cost = text_input_cost + audio_input_cost
        
        # Calculate output cost
        output_cost = (total_output_tokens / 1_000_000) * output_price.price_per_unit
        
        # Total cost
        total_cost = total_input_cost + output_cost
        
        print(f"   💰 LLM COSTS:")
        print(f"      text_input_cost: ({text_input_tokens:.2f} / 1M) × ${input_price.price_per_unit} = ${text_input_cost:.6f}")
        print(f"      audio_input_cost: ({audio_input_tokens:.2f} / 1M) × ${effective_audio_input_price.price_per_unit} = ${audio_input_cost:.6f}")
        print(f"      total_input_cost: ${total_input_cost:.6f}")
        print(f"      output_cost: ({total_output_tokens:.2f} / 1M) × ${output_price.price_per_unit} = ${output_cost:.6f}")
        print(f"      total_llm_cost: ${total_cost:.6f}")
        
        # ============================================
        # PART 4: UPDATE USER IN DATABASE
        # ============================================
        print(f"\n📊 PART 4: UPDATE USER DATABASE")
        print(f"{'-'*80}")
        
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        
        if not user:
            print(f"⚠️ User not found: {user_id}")
            return {"llm_cost": 0.0, "total_cost": 0.0, "error": f"User not found"}
        
        # Update user costs
        user.llm_cost = (user.llm_cost or 0.0) + total_cost
        user.total_cost = (user.total_cost or 0.0) + total_cost
        await db.commit()
        
        print(f"   ✅ llm_cost added: ${total_cost:.6f}")
        print(f"   ✅ total_cost added: ${total_cost:.6f}")
        print(f"   User {user_id} updated successfully")
        
        print(f"\n{'='*80}")
        print(f"✅ SPEAKING FEEDBACK COST RECORDED: ${total_cost:.6f}")
        print(f"{'='*80}\n")
        
        return {
            "llm_cost": round(total_cost, 6),
            "total_cost": round(total_cost, 6),
            "error": None
        }
        
    except Exception as e:
        print(f"❌ Error recording feedback cost: {e}")
        import traceback
        traceback.print_exc()
        return {"llm_cost": 0.0, "total_cost": 0.0, "error": str(e)}


async def record_translation_cost(
    user_id: str,
    translation_text: str,
    db = None
) -> dict:
    """
    Record cost for vocabulary translation
    
    Args:
        user_id: User ID
        translation_text: Text that was translated
        db: Database session
    
    Returns:
        Dictionary with cost info
    """
    try:
        # Translation cost is based on character count
        # Simple fixed cost per character
        COST_PER_CHAR = 0.0001  # $0.0001 per character
        
        char_count = len(translation_text)
        translation_cost = max(0.001, char_count * COST_PER_CHAR)  # Minimum $0.001
        
        if db:
            from sqlalchemy import select
            from .models import User
            
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            
            if user:
                user.llm_cost = (user.llm_cost or 0.0) + translation_cost
                user.total_cost = (user.total_cost or 0.0) + translation_cost
                await db.commit()
        
        return {
            "total_cost": round(translation_cost, 6),
            "char_count": char_count,
            "error": None
        }
    except Exception as e:
        print(f"❌ Error recording translation cost: {e}")
        return {"total_cost": 0.0, "error": str(e)}