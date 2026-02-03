import os
import hashlib
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
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
    generate: bool = True
) -> str | None:
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
            db.add(TTSLog(language=lang, chars=char_count, source='cache'))
            await db.commit()
        return web_path

    if not generate:
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
                db.add(TTSLog(language=lang, chars=char_count, source='cache'))
                await db.commit()
            return web_path
        
        # Тепер генеруємо (тільки один запит одночасно)
        # Використовуємо оригінальний текст для TTS (щоб зберегти регістр та інтонацію)
        # Визначаємо job_name на основі source
        if source == 'vocabulary':
            job_name_map = {'de': 'vocabulary_tts_de', 'uk': 'vocabulary_tts_ua', 'en': 'vocabulary_tts_en'}
        else:  # texts
            job_name_map = {'de': 'vocabulary_tts_de', 'uk': 'vocabulary_tts_ua', 'en': 'vocabulary_tts_en'}
        
        job_name = job_name_map.get(lang, 'generate_text_audio')
        
        audio_content = await services.get_tts_audio(text, lang, db=db, job_name=job_name)
        
        if audio_content:
            # Billing: Списуємо кредити тільки за генерацію (якщо не в фоновому режимі)
            if deduct_credits:
                provider = 'google'
                cost = billing.calculate_tts_cost(text, provider)
                await billing.deduct_credits(user_id, cost)
            
            # Cost Calculation: Record TTS generation cost (тільки при генерації, не з кешу!)
            from . import cost_calculation
            await cost_calculation.record_tts_text_generation_cost(
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
                db.add(TTSLog(language=lang, chars=char_count, source='api'))
                await db.commit()
                
            return web_path
        
        print(f"ERROR: Failed to generate TTS audio for '{text}' in {lang}")
        return None
