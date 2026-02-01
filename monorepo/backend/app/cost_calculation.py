"""
Cost calculation module for tracking API usage and resource consumption.
Supports calculations for LLM models (tokens) and TTS models (characters).
"""

from typing import Literal

# Constants for LLM token calculation
# Characters to tokens ratio per language for text output
LANGUAGE_CHAR_TO_TOKEN_RATIO = {
    "en": 4.0,      # English: 4.1 characters = 1 token
    "de": 3.5,      # German: 3.6 characters = 1 token
    "uk": 2.2,      # Ukrainian: 1.6 characters = 1 token
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
        if user:
            user.llm_cost = (user.llm_cost or 0.0) + total_cost
            user.total_cost = (user.total_cost or 0.0) + total_cost
            await db.commit()
            
            print(f"✅ Grammar explanation cost recorded: ${total_cost:.6f} for user {user_id}")
            return total_costalar_one_or_none()
        
        if user:
            user.llm_cost = (user.llm_cost or 0.0) + total_cost
            user.total_cost = (user.total_cost or 0.0) + total_cost
            await db.commit()
            
            return total_cost
        
        return 0.0
        
    except Exception as e:
        print(f"❌ Error recording grammar explanation cost: {e}")
        return 0.0

