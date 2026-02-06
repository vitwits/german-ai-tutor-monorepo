#!/usr/bin/env python3
"""
Генератор аудіо для нової системи
Читає речення з БД та генерує аудіо файли у /static/audio/sentences
"""
import os
import sys
import random
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import texttospeech
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import asyncio

# Налаштування
BACKEND_DIR = Path(__file__).parent.parent  # /monorepo/backend
BASE_DIR = BACKEND_DIR.parent  # /monorepo
load_dotenv(BASE_DIR / ".env")

# Налаштування Google Cloud credentials
google_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service-account.json")
if not Path(google_creds).is_absolute():
    google_creds = BASE_DIR / google_creds
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(google_creds)

sys.path.insert(0, str(BACKEND_DIR))

from app.models import TempSentence, Sentence, SentenceBatch, Base, AIPreference, TTSVoice
from app.database import DATABASE_URL

# Папка для аудіо
STATIC_AUDIO_DIR = BACKEND_DIR / "static" / "audio" / "sentences"

async def get_tts_voices_for_lang(lang: str, db: AsyncSession) -> list[str]:
    """
    Отримує обидва голоси (male + female) для мови з ai_preferences.
    
    Дивимося на ai_preferences де page='sentences' і шукаємо записи для цієї мови.
    lang — мова як 'de', 'en', 'uk' (як передається з TempSentence)
    
    tts_voices.lang містить скорочені коди: 'DE', 'EN', 'UA'
    """
    from sqlalchemy import and_
    
    # Маппим uk → UA, en → EN, de → DE для пошуку в tts_voices за мовою
    lang_code_map = {
        'de': 'DE',
        'en': 'EN',
        'uk': 'UA'
    }
    lang_code = lang_code_map.get(lang.lower(), lang.upper())
    
    # Шукаємо голоси для цієї мови в ai_preferences де page='sentences'
    result = await db.execute(
        select(TTSVoice.voice_name).join(
            AIPreference, AIPreference.tts_voice_id == TTSVoice.id
        ).where(
            and_(
                AIPreference.page == 'sentences',
                AIPreference.model_type == 'tts',
                TTSVoice.lang == lang_code,  # Точне порівняння: 'EN' == 'EN'
                TTSVoice.is_active == True
            )
        ).order_by(AIPreference.gender)  # Male comes before Female alphabetically
    )
    voices = result.scalars().all()
    
    return list(voices)

def generate_audio_file(text, lang, filepath, voice_name: str):
    """Генерує аудіо файл з вказаним голосом"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    client = texttospeech.TextToSpeechClient()
    
    language_code = voice_name[:5]
    
    s_input = texttospeech.SynthesisInput(text=text)
    
    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=voice_name
    )
    
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.OGG_OPUS
    )
    
    try:
        response = client.synthesize_speech(
            input=s_input, voice=voice, audio_config=audio_config
        )
        
        with open(filepath, "wb") as out:
            out.write(response.audio_content)
        return True
    except Exception as e:
        print(f"Error synthesizing {lang}: {e}")
        return False

async def generate_audio_for_batch(batch_id):
    """
    Генерує аудіо для тимчасових речень у батчі та створює фінальні записи в таблиці sentences
    """
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session() as db:
        # Отримуємо голоси для кожної мови з ai_preferences (male + female пари)
        voices = {}
        for lang in ['de', 'en', 'uk']:
            voice_list = await get_tts_voices_for_lang(lang, db)
            if not voice_list:
                print(f"⚠️  Warning: No voices found for {lang} in ai_preferences")
                voices[lang] = []
            else:
                voices[lang] = voice_list
        
        # Перевіркимо що всі мови мають голоси
        for lang in ['de', 'en', 'uk']:
            if not voices[lang]:
                print(f"✗ Error: No voices configured for {lang} in ai_preferences")
                return
        
        # Отримуємо батч
        result = await db.execute(
            select(SentenceBatch).where(SentenceBatch.id == batch_id)
        )
        batch = result.scalar_one_or_none()
        
        if not batch:
            print(f"Batch {batch_id} not found")
            return
        
        level = batch.level.lower()
        
        # Отримуємо всі ТИМЧАСОВІ речення батча
        result = await db.execute(
            select(TempSentence).where(TempSentence.batch_id == batch_id)
        )
        temp_sentences = result.scalars().all()
        
        print(f"\nGenerating audio for {len(temp_sentences)} sentences in batch {batch_id} ({level})...\n")
        
        success_count = 0
        final_sentences = []
        
        for idx, temp_sentence in enumerate(temp_sentences, 1):
            print(f"[{idx}/{len(temp_sentences)}] {temp_sentence.de[:40]}...", end="")
            
            # Шляхи для аудіо (відносні до /static)
            file_prefix = f"{idx:04d}"
            path_de_rel = f"{level}/{file_prefix}_de.ogg"
            path_en_rel = f"{level}/{file_prefix}_en.ogg"
            path_uk_rel = f"{level}/{file_prefix}_uk.ogg"
            
            # Абсолютні шляхи для запису файлів
            path_de_abs = STATIC_AUDIO_DIR / level / f"{file_prefix}_de.ogg"
            path_en_abs = STATIC_AUDIO_DIR / level / f"{file_prefix}_en.ogg"
            path_uk_abs = STATIC_AUDIO_DIR / level / f"{file_prefix}_uk.ogg"
            
            # Генеруємо аудіо з динамічним вибором голосу (50/50 male/female)
            voice_de = random.choice(voices['de'])
            voice_en = random.choice(voices['en'])
            voice_uk = random.choice(voices['uk'])
            
            print(f"\n    DE: {voice_de} | EN: {voice_en} | UA: {voice_uk}", end=" ")
            
            de_ok = generate_audio_file(temp_sentence.de, 'de', str(path_de_abs), voice_de)
            en_ok = de_ok and generate_audio_file(temp_sentence.en, 'en', str(path_en_abs), voice_en)
            uk_ok = en_ok and generate_audio_file(temp_sentence.uk, 'uk', str(path_uk_abs), voice_uk)
            
            if de_ok and en_ok and uk_ok:
                # Створюємо ФІНАЛЬНУ запись у таблиці sentences БЕЗ встановлення id
                final_sentence = Sentence(
                    text_de=temp_sentence.de,
                    text_en=temp_sentence.en,
                    text_uk=temp_sentence.uk,
                    audio_de=path_de_rel,
                    audio_en=path_en_rel,
                    audio_uk=path_uk_rel,
                    level=level.upper(),
                    topic=temp_sentence.topic
                )
                final_sentences.append(final_sentence)
                db.add(final_sentence)
                success_count += 1
                print("✓")
            else:
                print("✗")
        
        # Оновлюємо батч
        batch.status = "audio_ready"
        await db.commit()
        
        print(f"\n✓ Successfully generated audio and created {success_count} final sentences")
        print(f"✓ Batch {batch_id} is now ready for use")

async def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_audio_batch.py <batch_id>")
        sys.exit(1)
    
    try:
        batch_id = int(sys.argv[1])
    except ValueError:
        print("Error: batch_id must be a number")
        sys.exit(1)
    
    await generate_audio_for_batch(batch_id)

if __name__ == "__main__":
    asyncio.run(main())
