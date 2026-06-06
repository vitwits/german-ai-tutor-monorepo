from sqlalchemy import select
from .database import AsyncSessionLocal
from .models import User

PRICING = {
    # --- ТЕКСТ (Gemini Flash 2.5 lite) ---
    'ai_request_fixed': 0.1,    # Мінімальна плата за звернення до AI
    'translation_per_char': 0.001,  # $1 за 1M символів

    # --- АУДІО (TTS) ---
    'tts_google_per_char': 0.004,  # $4 за 1M символів
    'tts_azure_per_char': 0.015,  # $15 за 1M символів

    # --- SPEAKING (Speech-to-Text) ---
    'stt_fixed_request': 6.0,  # $0.006 за транзакцію STT (до 15 сек)
    'speaking_evaluation': 5.0,  # Вартість оцінки вимови

    # --- GENERATION ---
    'lesson_generation': 2.0,  # Вартість генерації уроку
}


def calculate_tts_cost(text, provider='google'):
    if not text:
        return 0
    length = len(text)
    rate = PRICING['tts_azure_per_char'] if provider == 'azure' else PRICING['tts_google_per_char']
    cost = length * rate
    return max(0.1, round(cost, 3))


def calculate_translation_cost(text):
    if not text:
        return 0
    length = len(text)
    cost = length * PRICING['translation_per_char']
    return max(0.01, round(cost, 3))


async def deduct_credits(user_id: str, cost: float) -> float | None:
    if cost <= 0:
        return None
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user: return 0.0
        
        new_balance = max(0.0, user.credits - cost)
        user.credits = new_balance
        await session.commit()
        return round(new_balance, 2)