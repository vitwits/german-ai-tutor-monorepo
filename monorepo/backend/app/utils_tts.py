import os
import hashlib
from sqlalchemy.ext.asyncio import AsyncSession
from . import services, billing
from .models import TTSLog

# Шлях до папки static/audio (відносно цього файлу)
# Ми виходимо з monorepo/backend/app -> monorepo/backend -> monorepo -> ROOT -> static
# Це дозволяє використовувати ВЖЕ ІСНУЮЧИЙ кеш зі старого проекту
STATIC_AUDIO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../static/audio"))
CACHE_DIR = os.path.join(STATIC_AUDIO_DIR, "cache")

async def get_cached_or_generate_tts(
    text: str, 
    lang: str, 
    user_id: str, 
    db: AsyncSession, 
    log_stats: bool = False, 
    generate: bool = True
) -> str | None:
    """
    Повертає URL аудіофайлу. Якщо файлу немає - генерує його, зберігає і списує кредити.
    Використовує логіку хешування та шардінгу (перші 2 символи хешу) як у старому проекті.
    """
    if not text: return None
    
    # 1. Нормалізація та хешування (ідентично до старого app.py)
    clean_text = text.lower().strip()
    file_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()
    shard = file_hash[:2]
    
    # Шляхи: static/audio/cache/{lang}/{shard}/{file_hash}.ogg
    target_dir = os.path.join(CACHE_DIR, lang, shard)
    filename = f"{file_hash}.ogg"
    filepath = os.path.join(target_dir, filename)
    
    # URL для фронтенду
    web_path = f"/static/audio/cache/{lang}/{shard}/{filename}"
    
    char_count = len(text)

    # 2. Перевірка наявності файлу (використовуємо старий кеш)
    if os.path.exists(filepath):
        if log_stats:
            # Логуємо використання кешу (без списання кредитів)
            db.add(TTSLog(language=lang, chars=char_count, source='cache'))
            await db.commit()
        return web_path

    if not generate:
        return None

    # 3. Генерація (якщо файлу немає)
    # Використовуємо оригінальний текст для TTS (щоб зберегти регістр та інтонацію)
    audio_content = services.get_tts_audio(text, lang)
    
    if audio_content:
        # Billing: Списуємо кредити тільки за генерацію
        provider = 'google'
        cost = billing.calculate_tts_cost(text, provider)
        await billing.deduct_credits(user_id, cost)
        
        # Збереження файлу (створюємо папку шарду, якщо її немає)
        os.makedirs(target_dir, exist_ok=True)
        with open(filepath, "wb") as out:
            out.write(audio_content)
            
        if log_stats:
            db.add(TTSLog(language=lang, chars=char_count, source='api'))
            await db.commit()
            
        return web_path
    
    return None
