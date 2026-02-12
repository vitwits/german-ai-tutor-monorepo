import os
import hashlib
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from . import services, billing
from .models import TTSLog

# Шлях до папки static/audio (відносно цього файлу)
# Структура: 
#   - vocabulary: static/audio/vocabulary/{lang}/{shard}/{hash}.ogg (словник)
#   - texts: static/audio/texts/{lang}/{shard}/{hash}.ogg (речення в текстах)
STATIC_AUDIO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../static/audio"))
VOCABULARY_DIR = os.path.join(STATIC_AUDIO_DIR, "vocabulary")
TEXTS_DIR = os.path.join(STATIC_AUDIO_DIR, "texts")

# Глобальні lock'и для попередження дублювання генерацій
_tts_generation_locks: dict[str, asyncio.Lock] = {}

async def log_tts_usage(
    db: AsyncSession,
    language: str,
    chars: int,
    operation_type: str  # 'cache' або 'api'
) -> None:
    """
    Оновлює статистику використання TTS в агрегованому рядку.
    
    Args:
        db: Сесія бази даних
        language: Код мови ('de', 'en', 'uk')
        chars: Кількість символів
        operation_type: 'cache' або 'api'
    """
    # Отримуємо або створюємо єдиний агрегований рядок
    result = await db.execute(select(TTSLog))
    log_entry = result.scalar_one_or_none()
    
    if not log_entry:
        log_entry = TTSLog()
        db.add(log_entry)
    
    # Оновлюємо відповідні лічильники на основі мови та типу операції
    # Лічильники названі як: {lang}_{operation}_requests та {lang}_{operation}_chars
    requests_field = f"{language}_{operation_type}_requests"
    chars_field = f"{language}_{operation_type}_chars"
    
    # Оновлюємо значення, поточне значення + 1 для requests та + chars для chars
    current_requests = getattr(log_entry, requests_field)
    current_chars = getattr(log_entry, chars_field)
    
    setattr(log_entry, requests_field, current_requests + 1)
    setattr(log_entry, chars_field, current_chars + chars)
    
    await db.commit()

def delete_sentence_audio_cache(text: str, lang: str = 'de') -> bool:
    """
    Видаляє кешоване аудіо речення (використовується при видаленні тексту).
    Речення кешуються в /static/audio/texts/{lang}/{shard}/{hash}.ogg
    
    Args:
        text: Текст речення
        lang: Мова (за замовчуванням 'de' для речень у текстах)
    
    Returns:
        True якщо файл був видалений, False якщо файлу не було
    """
    if not text:
        return False
    
    # Нормалізація та хешування (ідентично до get_cached_or_generate_tts)
    clean_text = text.lower().strip()
    file_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()
    shard = file_hash[:2]
    
    # Для текстів - використовуємо TEXTS_DIR
    filepath = os.path.join(TEXTS_DIR, lang, shard, f"{file_hash}.ogg")
    
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            return True
        except Exception as e:
            print(f"Error deleting audio cache: {e}")
            return False
    
    return False

async def get_cached_or_generate_tts(
    text: str, 
    lang: str, 
    user_id: str, 
    db: AsyncSession,
    source: str = 'texts',  # 'texts' для речень у текстах, 'vocabulary' для словника
    deduct_credits: bool = True,  # False для фонової генерації (кредити вже списані)
    log_stats: bool = False, 
    generate: bool = True,
    return_cost: bool = False  # Повертати кортеж (url, cost) замість просто url
) -> str | None | tuple:
    """
    Повертає URL аудіофайлу. Якщо файлу немає - генерує його, зберігає і списує кредити.
    Використовує логіку хешування та шардінгу (перші 2 символи хешу) як у старому проекті.
    
    Має вбудовану синхронізацію (lock) щоб уникнути дублювання генерацій при паралельних запитах.
    
    Args:
        text: Текст для озвучення
        lang: Мова ('de', 'uk', 'en')
        user_id: ID користувача (для списання кредитів)
        db: AsyncSession для БД
        source: 'texts' (речення у текстах) або 'vocabulary' (словник)
        deduct_credits: Списувати кредити (False для фонової генерації)
        log_stats: Логувати статистику
        generate: Генерувати якщо немає в кешу
        return_cost: Повертати кортеж (url, cost) замість просто url
        
    Returns:
        - Якщо return_cost=False: URL аудіо (str) або None
        - Якщо return_cost=True: (url, cost) кортеж або (None, 0.0)
    """
    if not text: return None
    
    # Вибираємо папку на основі source
    cache_base_dir = TEXTS_DIR if source == 'texts' else VOCABULARY_DIR
    
    # 1. Нормалізація та хешування (ідентично до старого app.py)
    clean_text = text.lower().strip()
    file_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()
    shard = file_hash[:2]
    
    # Шляхи: static/audio/{source}/{lang}/{shard}/{file_hash}.ogg
    target_dir = os.path.join(cache_base_dir, lang, shard)
    filename = f"{file_hash}.ogg"
    filepath = os.path.join(target_dir, filename)
    
    # URL для фронтенду
    web_path = f"/static/audio/{source}/{lang}/{shard}/{filename}"
    
    char_count = len(text)
    
    # Cache key для lock'а (source + lang + hash)
    cache_key = f"{source}:{lang}:{file_hash}"
    # 2. Перевірка наявності файлу в кешу
    if os.path.exists(filepath):
        if log_stats:
            # Логуємо використання кешу (без списання кредитів)
            await log_tts_usage(db, lang, char_count, 'cache')
        if return_cost:
            return (web_path, 0.0)  # Кеш - без вартості
        return web_path

    if not generate:
        if return_cost:
            return (None, 0.0)
        return None

    # 3. Генерація (якщо файлу немає)
    # Створюємо або беремо існуючий lock для цього файлу
    if cache_key not in _tts_generation_locks:
        _tts_generation_locks[cache_key] = asyncio.Lock()
    
    lock = _tts_generation_locks[cache_key]
    
    async with lock:
        # Перевіряємо знову (можливо інший запит уже згенерував поки ми чекали)
        if os.path.exists(filepath):
            if log_stats:
                # Логуємо використання кешу
                await log_tts_usage(db, lang, char_count, 'cache')
            if return_cost:
                return (web_path, 0.0)  # Кеш - без вартості
            return web_path
        
        # Тепер генеруємо (тільки один запит одночасно)
        # Використовуємо оригінальний текст для TTS (щоб зберегти регістр та інтонацію)
        # Визначаємо job_name на основі source
        if source == 'vocabulary':
            job_name_map = {'de': 'vocabulary_tts_de', 'uk': 'vocabulary_tts_ua', 'en': 'vocabulary_tts_en'}
        else:  # texts
            job_name_map = {'de': 'generate_text_audio', 'uk': 'generate_text_audio', 'en': 'generate_text_audio'}
        
        job_name = job_name_map.get(lang, 'generate_text_audio')
        
        audio_content = await services.get_tts_audio(text, lang, db=db, job_name=job_name)
        
        tts_cost = 0.0  # Initialize cost variable
        
        if audio_content:
            # Billing: Now handled by deduct_user_energy() in the endpoint
            # (No longer using credits system)
            
            # Cost Calculation: Record TTS generation cost (тільки при генерації, не з кешу!)
            from . import cost_calculation
            tts_cost = await cost_calculation.record_tts_text_generation_cost(
                user_id=user_id,
                text=text,
                lang=lang,
                job_name=job_name,
                db=db
            )
            
            # Збереження файлу (створюємо папку шарду, якщо її немає)
            os.makedirs(target_dir, exist_ok=True)
            with open(filepath, "wb") as out:
                out.write(audio_content)
                
            if log_stats:
                # Логуємо использання API
                await log_tts_usage(db, lang, char_count, 'api')
                
            if return_cost:
                return (web_path, tts_cost)
            return web_path
        
        print(f"ERROR: Failed to generate TTS audio for '{text}' in {lang}")
        if return_cost:
            return (None, 0.0)
        return None
