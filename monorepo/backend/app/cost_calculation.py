"""
Cost calculation module for tracking API usage and resource consumption.
Supports calculations for LLM models (tokens) and TTS models (characters).
"""

from typing import Literal

# Constants for LLM token calculation
# Characters to tokens ratio per language for text output
LANGUAGE_CHAR_TO_TOKEN_RATIO = {
    "en": 4.1,      # English: 4.1 characters = 1 token
    "de": 3.6,      # German: 3.6 characters = 1 token
    "uk": 1.6,      # Ukrainian: 1.6 characters = 1 token
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
