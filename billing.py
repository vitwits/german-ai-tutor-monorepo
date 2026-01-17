import math
from database import get_db

# КУРС: 1000 Credits = $1.00 USD
# 1 Credit = $0.001 (0.1 cent)

PRICING = {
    # --- ТЕКСТ (Gemini Flash 2.0) ---
    'ai_request_fixed': 0.1,      # Мінімальна плата за звернення до AI
    'translation_per_char': 0.001, # $1 за 1M символів
    
    # --- АУДІО (TTS) ---
    'tts_google_per_char': 0.004,  # $4 за 1M символів
    'tts_azure_per_char': 0.015,   # $15 за 1M символів
    
    # --- SPEAKING (Speech-to-Text) ---
    'stt_fixed_request': 6.0,      # $0.006 за транзакцію STT (до 15 сек)
    'speaking_evaluation': 5.0     # Вартість оцінки вимови
}

def calculate_tts_cost(text, provider='google'):
    """Розрахунок вартості озвучки тексту."""
    if not text: return 0
    length = len(text)
    rate = PRICING['tts_azure_per_char'] if provider == 'azure' else PRICING['tts_google_per_char']
    cost = length * rate
    return max(0.1, round(cost, 3))

def calculate_translation_cost(text):
    """Розрахунок вартості перекладу тексту."""
    if not text: return 0
    length = len(text)
    cost = length * PRICING['translation_per_char']
    return max(0.01, round(cost, 3))

def calculate_speaking_session_total(user_audio_duration_sec, ai_response_text, feedback_text):
    """
    РЕАЛЬНА вартість одного кроку в Speaking:
    1. STT (голос юзера) - беремо фікс, бо провайдери так тарифікують.
    2. AI (аналіз Gemini) - фікс.
    3. TTS (озвучка відповіді асистента) - рахуємо по символах.
    4. TTS (озвучка фідбеку) - рахуємо по символах.
    """
    # 1. Розпізнавання (STT)
    stt_cost = PRICING['stt_fixed_request']
    
    # 2. Робота інтелекту (Gemini)
    ai_cost = PRICING['ai_request_fixed']
    
    # 3. Озвучка правильної відповіді (зазвичай німецька/англійська - Google)
    response_tts = calculate_tts_cost(ai_response_text, provider='google')
    
    # 4. Озвучка фідбеку (зазвичай українська - Azure)
    feedback_tts = calculate_tts_cost(feedback_text, provider='azure')
    
    total_cost = stt_cost + ai_cost + response_tts + feedback_tts
    return round(total_cost, 2)

def deduct_credits(user_id, cost):
    """Списує кредити з балансу користувача."""
    if cost <= 0: return None

    with get_db() as conn:
        cur = conn.execute('SELECT credits FROM users WHERE id = ?', (user_id,)).fetchone()
        if not cur: return 0
        
        current_credits = cur['credits']
        new_balance = max(0.0, current_credits - cost)
        
        conn.execute('UPDATE users SET credits = ? WHERE id = ?', (new_balance, user_id))
        conn.commit()
        
        return round(new_balance, 2)