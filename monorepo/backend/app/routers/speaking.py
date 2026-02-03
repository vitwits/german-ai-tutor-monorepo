from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
import random

from ..database import get_db
from ..models import User, Sentence, UserBlockedSentence, UserFavoriteSentence, Vocabulary, Feedback
from ..schemas import ReportSentenceRequest, ToggleSentenceFavRequest, RemoveFavSentenceRequest
from ..dependencies import get_current_user
from .. import services
from ..services import deduct_user_energy

router = APIRouter(prefix="/api", tags=["speaking"])

@router.get("/speaking/next")
async def speaking_next(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Subquery to exclude blocked sentences
    blocked_sub = select(UserBlockedSentence.sentence_id).where(UserBlockedSentence.user_id == current_user.id)
    
    query = select(Sentence).where(
        Sentence.level == current_user.level,
        Sentence.reported == 0,  # Исключаем reported sentences для всех пользователей
        Sentence.id.not_in(blocked_sub)
    ).order_by(func.random()).limit(1)
    
    result = await db.execute(query)
    sentence = result.scalar_one_or_none()
    
    if not sentence:
        # Fallback: берем любую речение (но не reported и не blocked)
        result = await db.execute(
            select(Sentence).where(
                Sentence.reported == 0,
                Sentence.id.not_in(blocked_sub)
            ).order_by(func.random()).limit(1)
        )
        sentence = result.scalar_one_or_none()
        
    if not sentence:
        return {"error": "No sentences found"}

    # Check if favorite
    fav_res = await db.execute(select(UserFavoriteSentence).where(
        UserFavoriteSentence.user_id == current_user.id,
        UserFavoriteSentence.sentence_id == sentence.id
    ))
    is_fav = fav_res.scalar_one_or_none() is not None

    return {
        "sentence": sentence,
        "is_fav": is_fav
    }

@router.post("/evaluate_audio")
async def evaluate_audio(
    audio: UploadFile = File(...),
    original_text: str = Form(...),
    stop_type: str = Form(None),  # 'auto' or 'manual' - whether silence timeout or user button stopped recording
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    audio_bytes = await audio.read()
    lang_code = 'uk' if current_user.interface_language == 'ukr' else 'en'
    
    # Використовуємо динамічну модель з ai_preferences 'speaking_feedback' job
    result = await services.evaluate_audio_with_gemini(
        original_text, 
        audio_bytes, 
        lang_code, 
        db=db, 
        mime_type=audio.content_type,
        stop_type=stop_type  # Pass stop type for audio trimming decision
    )
    
    # Record cost (LLM input: text + audio, output: JSON with German transcription/correction)
    from ..cost_calculation import record_feedback_cost
    cost_result = await record_feedback_cost(
        user_id=current_user.id,
        feedback_data=result,
        db=db
    )
    
    spending_usd = cost_result.get("total_cost", 0)
    
    if cost_result.get("error"):
        print(f"⚠️ Cost calculation error: {cost_result['error']}")
        # Continue anyway - don't fail evaluation if cost calc fails
    
    # Deduct energy based on actual spending
    if spending_usd > 0:
        energy_result = await deduct_user_energy(db, current_user.id, spending_usd)
        if not energy_result.get("ok"):
            raise HTTPException(
                status_code=402,  # Payment Required
                detail=f"Insufficient energy: {energy_result.get('error')}"
            )
    
    # Calculate average
    avg = int((result.get('pronunciation_score', 0) + result.get('context_score', 0) + result.get('grammar_score', 0)) / 3)
    result['average_score'] = avg
    
    # Select feedback audio from DB
    fb_res = await db.execute(select(Feedback).where(
        Feedback.language == lang_code,
        Feedback.category == 'common',
        Feedback.min_score <= avg,
        Feedback.max_score >= avg
    ).order_by(func.random()).limit(1))
    
    fb_row = fb_res.scalar_one_or_none()
    if fb_row:
        result['feedback_audio_url'] = f"/static/audio/{fb_row.file_path}"

    # Return energy status
    from ..services import get_user_energy_status
    energy_status = await get_user_energy_status(db, current_user.id)
    
    # Add energy info to result for frontend
    if energy_status.get('ok'):
        # Get the actual UserBilling data for energy_left and daily_spending
        from sqlalchemy import select
        from ..models import UserBilling
        billing_result = await db.execute(select(UserBilling).where(UserBilling.user_id == current_user.id))
        user_billing = billing_result.scalar_one_or_none()
        if user_billing:
            result['energy'] = {
                'energy_left': user_billing.energy_left,
                'daily_spending': user_billing.daily_spending,
                'subscription_status': user_billing.subscription_status
            }
    
    return result

@router.post("/toggle_sentence_fav")
async def toggle_sentence_fav(req: ToggleSentenceFavRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    res = await db.execute(select(UserFavoriteSentence).where(
        UserFavoriteSentence.user_id == current_user.id,
        UserFavoriteSentence.sentence_id == req.id
    ))
    existing = res.scalar_one_or_none()
    
    if existing:
        await db.delete(existing)
        is_fav = False
    else:
        db.add(UserFavoriteSentence(user_id=current_user.id, sentence_id=req.id))
        is_fav = True
    await db.commit()
    return {"ok": True, "is_fav": is_fav}

@router.post("/remove_fav_sentence")
async def remove_fav_sentence(req: RemoveFavSentenceRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Here req.id is the ID from user_favorite_sentences table
    await db.execute(
        delete(UserFavoriteSentence)
        .where(UserFavoriteSentence.id == req.id, UserFavoriteSentence.user_id == current_user.id)
    )
    await db.commit()
    return {"ok": True}

@router.post("/report_sentence")
async def report_sentence(req: ReportSentenceRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # 1. Mark as reported globally
    await db.execute(
        update(Sentence).where(Sentence.id == req.id).values(reported=1)
    )
    # 2. Block for this user
    # Check if already blocked to avoid PK constraint error (though insert or ignore is better, simple check works)
    existing = await db.scalar(select(UserBlockedSentence).where(UserBlockedSentence.user_id == current_user.id, UserBlockedSentence.sentence_id == req.id))
    if not existing:
        db.add(UserBlockedSentence(user_id=current_user.id, sentence_id=req.id))
    
    await db.commit()
    return {"ok": True}