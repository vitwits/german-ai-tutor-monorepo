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


def is_error_response(status_code: int) -> bool:
    """
    Check if response status indicates an error that should not be charged.
    
    Args:
        status_code: HTTP status code
        
    Returns:
        True if error (400 or 500 range), False otherwise
    """
    return 400 <= status_code < 600


async def record_grammar_explanation_cost(
    user_id: str,
    prompt_text: str,
    response_text: str,
    model_id: str,
    input_lang: str = "en",
    output_lang: str = "uk",
    db=None
) -> float:
    """
    Record cost for grammar explanation generation and update user's llm_cost.
    
    Args:
        user_id: User ID to charge
        prompt_text: Input prompt text (input data)
        response_text: Generated response text (output data)
        model_id: Model ID used for generation (e.g., 'gemini-2.5-flash-lite')
        input_lang: Language of input prompt ('en', 'de', 'uk')
        output_lang: Language of output response ('en', 'de', 'uk')
        db: AsyncSession for database operations
        
    Returns:
        Total cost calculated for input and output combined
    """
    if not db or not response_text:
        return 0.0
    
    try:
        # DEBUG: Print received parameters
        print(f"\n🔍 DEBUG record_grammar_explanation_cost:")
        print(f"   user_id: {user_id}")
        print(f"   model_id: {model_id}")
        print(f"   input_lang: {input_lang}")
        print(f"   output_lang: {output_lang}")
        print(f"   prompt_text length: {len(prompt_text)} chars")
        print(f"   response_text length: {len(response_text)} chars")
        print(f"\n   📝 FULL INPUT TEXT:\n{prompt_text}\n")
        print(f"   📝 FULL OUTPUT TEXT:\n{response_text}\n")
        
        # Step 1: Calculate tokens for input and output
        input_tokens = calculate_text_output_tokens(prompt_text, input_lang)
        output_tokens = calculate_text_output_tokens(response_text, output_lang)
        
        print(f"🔍 DEBUG tokens calculated:")
        print(f"   input_tokens: {input_tokens:.2f}")
        print(f"   output_tokens: {output_tokens:.2f}\n")
        
        # Step 2: Get LLM model info from database
        from sqlalchemy import select
        from .models import LLMModel, LLMPrice
        
        # Find the model by model_id
        model_result = await db.execute(
            select(LLMModel).where(LLMModel.model_id == model_id)
        )
        model = model_result.scalar_one_or_none()
        
        if not model:
            print(f"⚠️ Model not found: {model_id}")
            return 0.0
        
        # Step 3: Get prices for input and output
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
        
        # Step 4: Calculate total cost
        # Price is per 1 million tokens, so: (tokens / 1_000_000) * price_per_unit
        input_cost = (input_tokens / 1_000_000) * input_price.price_per_unit
        output_cost = (output_tokens / 1_000_000) * output_price.price_per_unit
        total_cost = input_cost + output_cost
        
        print(f"🔍 DEBUG pricing found:")
        print(f"   input_price (per 1M tokens): ${input_price.price_per_unit}")
        print(f"   output_price (per 1M tokens): ${output_price.price_per_unit}")
        print(f"   input_cost: ${input_cost:.6f}")
        print(f"   output_cost: ${output_cost:.6f}")
        print(f"   total_cost: ${total_cost:.6f}\n")
        
        # Step 5: Update user's llm_cost
        from .models import User
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        
        if user:
            user.llm_cost = (user.llm_cost or 0.0) + total_cost
            user.total_cost = (user.total_cost or 0.0) + total_cost
            await db.commit()
            
            print(f"✅ Grammar explanation cost recorded: ${total_cost:.6f} for user {user_id}")
            return total_cost
        
        return 0.0
        
    except Exception as e:
        print(f"❌ Error recording grammar explanation cost: {e}")
        return 0.0


async def record_text_generation_cost(
    user_id: str,
    prompt_text: str,
    response_text: str,
    model_id: str,
    db=None
) -> float:
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
        Total cost calculated for input and all output languages combined
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
        
        # Step 2: Parse JSON response and extract text by language
        data = json.loads(response_text)
        
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
            return total_cost
        
        return 0.0
        
    except Exception as e:
        print(f"❌ Error recording text generation cost: {e}")
        import traceback
        traceback.print_exc()
        return 0.0
