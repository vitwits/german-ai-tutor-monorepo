import json
import random

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete, and_

from ..database import get_db
from ..models import User, Sentence, UserBlockedSentence, UserFavoriteSentence, Vocabulary, Feedback, UserBilling, Lesson, UserLesson, LessonAudio
from ..schemas import ReportSentenceRequest, ToggleSentenceFavRequest, RemoveFavSentenceRequest
from ..dependencies import get_current_user
from .. import services
from ..services import deduct_user_energy, get_user_energy_status
from ..utils_tts import get_cached_or_generate_tts

router = APIRouter(prefix="/api", tags=["speaking"])


def _normalize_audio_path(audio_path: str | None) -> str | None:
    if not audio_path:
        return None
    if audio_path.startswith("http") or audio_path.startswith("/"):
        return audio_path
    if audio_path.startswith("static/audio/"):
        return f"/{audio_path}"
    if audio_path.startswith("audio/"):
        return f"/static/{audio_path}"
    return f"/static/audio/{audio_path}"


def _sentence_text(sentence_data: dict | str | None, keys: list[str]) -> str:
    if not isinstance(sentence_data, dict):
        return ""
    for key in keys:
        value = sentence_data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


async def _get_lesson_audio_url(
    lesson_id: str,
    sentence_index: int,
    lang: str,
    sentence_text: str,
    db: AsyncSession,
    user_id: str,
) -> str | None:
    existing = await db.execute(
        select(LessonAudio).where(
            and_(
                LessonAudio.lesson_id == lesson_id,
                LessonAudio.sentence_index == sentence_index,
                LessonAudio.lang == lang,
                LessonAudio.status == "generated",
            )
        )
    )
    row = existing.scalar_one_or_none()
    if row and row.audio_path:
        return _normalize_audio_path(row.audio_path)

    if not sentence_text:
        return None

    # Cache-first lookup only (generate=False) to avoid legacy pre-generation flow.
    return await get_cached_or_generate_tts(
        sentence_text,
        lang,
        user_id,
        db,
        source="texts",
        generate=False,
    )


async def _build_lesson_sentence_for_user(
    db: AsyncSession,
    current_user: User,
):
    lessons_result = await db.execute(
        select(Lesson)
        .join(UserLesson, UserLesson.lesson_id == Lesson.id)
        .where(
            UserLesson.user_id == current_user.id,
            Lesson.level == current_user.level,
        )
        .order_by(func.random())
        .limit(25)
    )
    lessons = lessons_result.scalars().all()
    if not lessons:
        return None

    source_lang = "uk" if current_user.interface_language == "ukr" else "en"

    for lesson in lessons:
        try:
            lesson_sentences = json.loads(lesson.content_json or "[]")
        except Exception:
            lesson_sentences = []

        if not isinstance(lesson_sentences, list) or not lesson_sentences:
            continue

        valid_indices = []
        for idx, row in enumerate(lesson_sentences):
            text_de = _sentence_text(row, ["de", "text_de"])
            text_en = _sentence_text(row, ["en", "text_en"])
            text_uk = _sentence_text(row, ["uk", "ua", "ukr", "text_uk"])
            source_text = text_uk if source_lang == "uk" else text_en
            if text_de and source_text:
                valid_indices.append((idx, text_de, text_en, text_uk))

        if not valid_indices:
            continue

        sentence_index, text_de, text_en, text_uk = random.choice(valid_indices)

        audio_de = await _get_lesson_audio_url(
            lesson.id,
            sentence_index,
            "de",
            text_de,
            db,
            current_user.id,
        )
        audio_en = await _get_lesson_audio_url(
            lesson.id,
            sentence_index,
            "en",
            text_en,
            db,
            current_user.id,
        ) if text_en else None
        audio_uk = await _get_lesson_audio_url(
            lesson.id,
            sentence_index,
            "uk",
            text_uk,
            db,
            current_user.id,
        ) if text_uk else None

        return {
            "id": f"{lesson.id}:{sentence_index}",
            "lesson_id": lesson.id,
            "sentence_index": sentence_index,
            "text_de": text_de,
            "text_en": text_en,
            "text_uk": text_uk,
            "audio_de": audio_de,
            "audio_en": audio_en,
            "audio_uk": audio_uk,
        }

    return None

@router.get("/speaking/next")
async def speaking_next(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sentence = await _build_lesson_sentence_for_user(db, current_user)
    if not sentence:
        return {
            "error": "no_sentences_for_level",
        }

    return {
        "sentence": sentence,
        "is_fav": False,
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
    energy_status = await get_user_energy_status(db, current_user.id)
    
    # Add energy info to result for frontend
    if energy_status.get('ok'):
        # Get the actual UserBilling data for energy_left and daily_spending
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