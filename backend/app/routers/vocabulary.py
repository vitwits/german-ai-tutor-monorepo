import uuid
import re
import math
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, update, delete

from ..database import get_db
from ..models import User, Vocabulary, ExplainedWord, UserFavoriteSentence, Sentence, ReportedLesson, UserBilling
from ..schemas import VocabUpdateRequest, VocabRemoveRequest, ToggleFavRequest, VocabProgressRequest, QuickTranslateRequest, ExplainWordRequest, AddCustomWordRequest, VocabWordSchema
from ..dependencies import get_current_user
from .. import services
from ..cost_calculation import record_translation_cost
from ..services import deduct_user_energy
from ..utils_tts import get_cached_or_generate_tts

router = APIRouter(prefix="/api", tags=["vocabulary"])

def remove_duplicate_parts(translation_string):
    if not translation_string:
        return ""
    parts = [part.strip() for part in translation_string.split(',')]
    parts = [p for p in parts if p]
    
    unique_list = []
    seen = set()
    for p in parts:
        if p not in seen:
            unique_list.append(p)
            seen.add(p)
            
    final_parts = []
    for i, p_a in enumerate(unique_list):
        words_a = p_a.split()
        if not words_a: continue
        first_a = words_a[0].lower()
        
        is_redundant = False
        for j, p_b in enumerate(unique_list):
            if i == j: continue
            words_b = p_b.split()
            if not words_b: continue
            
            if words_b[0].lower() == first_a and len(words_b) > len(words_a):
                is_redundant = True
                break
        
        if not is_redundant:
            final_parts.append(p_a)
            
    return ', '.join(final_parts)

@router.get("/vocab")
async def get_vocab_list(
    page: int = 1,
    per_page: int = 36,
    q: str = "",
    levels: str = None,
    mode: str = "words", # 'words' or 'sentences'
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    offset = (page - 1) * per_page

    if mode == 'sentences':
        # Логіка для улюблених речень
        query = select(Sentence, UserFavoriteSentence.id.label("fav_id"), UserFavoriteSentence.created_at)\
            .join(UserFavoriteSentence, Sentence.id == UserFavoriteSentence.sentence_id)\
            .where(UserFavoriteSentence.user_id == current_user.id)
        
        count_query = select(func.count()).select_from(UserFavoriteSentence).where(UserFavoriteSentence.user_id == current_user.id)
        
        if q:
            search_pattern = f"%{q}%"
            query = query.where(or_(Sentence.text_de.like(search_pattern), Sentence.text_uk.like(search_pattern), Sentence.text_en.like(search_pattern)))
            count_query = count_query.where(or_(Sentence.text_de.like(search_pattern), Sentence.text_uk.like(search_pattern), Sentence.text_en.like(search_pattern)))
        
        if levels:
            lvl_list = [l for l in levels.split(',') if l in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']]
            if lvl_list:
                query = query.where(Sentence.level.in_(lvl_list))
                count_query = count_query.where(Sentence.level.in_(lvl_list))
        
        query = query.order_by(UserFavoriteSentence.created_at.desc()).offset(offset).limit(per_page)
        
        total = (await db.execute(count_query)).scalar_one()
        rows = (await db.execute(query)).all()
        
        sentences = []
        lang_key = 'text_uk' if current_user.interface_language == 'ukr' else 'text_en'
        audio_key = 'audio_uk' if current_user.interface_language == 'ukr' else 'audio_en'

        for row in rows:
            s = row.Sentence
            sentences.append({
                "id": s.id,
                "text_de": s.text_de,
                "display_trans": getattr(s, lang_key) or s.text_en,
                "audio_de": s.audio_de,
                "display_audio": getattr(s, audio_key),
                "fav_id": row.fav_id
            })
            
        return {"items": sentences, "total": total, "pages": math.ceil(total / per_page)}

    else:
        # Логіка для слів
        query = select(Vocabulary).where(Vocabulary.user_id == current_user.id, Vocabulary.is_favorite == 1)
        count_query = select(func.count()).select_from(Vocabulary).where(Vocabulary.user_id == current_user.id, Vocabulary.is_favorite == 1)

        if q:
            search = f"%{q}%"
            query = query.where(or_(Vocabulary.display.like(search), Vocabulary.ua.like(search), Vocabulary.en.like(search)))
            count_query = count_query.where(or_(Vocabulary.display.like(search), Vocabulary.ua.like(search), Vocabulary.en.like(search)))

        if levels:
            lvl_list = [l for l in levels.split(',') if l in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']]
            if lvl_list:
                query = query.where(Vocabulary.level.in_(lvl_list))
                count_query = count_query.where(Vocabulary.level.in_(lvl_list))

        total = (await db.execute(count_query)).scalar_one()
        result = await db.execute(query.order_by(Vocabulary.created_at.desc()).offset(offset).limit(per_page))
        words = result.scalars().all()
        
        # Transform to dicts and add display_trans and audio URLs
        items_data = []
        target_lang = 'uk' if current_user.interface_language == 'ukr' else 'en'
        
        for w in words:
            # Convert SQLAlchemy model to dict (or construct manually to be safe)
            item = VocabWordSchema.model_validate(w)
            # Add computed field
            item.display_trans = w.ua if target_lang == 'uk' else w.en
            item.display_ctx_trans = w.ctx_ua if target_lang == 'uk' else w.ctx_en
            
            # Add audio URLs (check cache, don't generate)
            audio_de = await get_cached_or_generate_tts(w.display, 'de', current_user.id, db, source='vocabulary', generate=False)
            item.audio_de_url = audio_de
            
            trans = item.display_trans
            trans_urls = []
            if trans:
                parts = [p.strip() for p in re.split(r'[,;]', trans) if p.strip()]
                for part in parts:
                    url = await get_cached_or_generate_tts(part, target_lang, current_user.id, db, source='vocabulary', generate=False)
                    if url: trans_urls.append(url)
            item.audio_trans_urls = trans_urls
            
            items_data.append(item)

        return {"items": items_data, "total": total, "pages": math.ceil(total / per_page)}

@router.get("/vocab/session")
async def vocab_session(
    mode: str = "study",  # 'study' або 'review'
    levels: str = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Study Mode: рандомна вибірка всіх улюблених слів
    Review Mode: розумна вибірка - OVERDUE > NEW+FREQUENT > NEW+INFREQUENT > FUTURE+FREQUENT
    """
    
    now = datetime.utcnow()
    base_query = select(Vocabulary).where(
        Vocabulary.user_id == current_user.id,
        Vocabulary.is_favorite == 1
    )
    
    if levels:
        lvl_list = [l for l in levels.split(',') if l]
        if lvl_list: 
            base_query = base_query.where(Vocabulary.level.in_(lvl_list))
    
    # ========== STUDY MODE: Випадкова вибірка всіх слів ==========
    if mode == "study":
        # Отримуємо ВСІ слова та сортуємо рандомно
        query = base_query.order_by(func.random())
        result = await db.execute(query)
        words = result.scalars().all()
        
    # ========== REVIEW MODE: Розумна вибірка за пріоритетами ==========
    else:
        # Категорія 1: OVERDUE (next_review < now)
        overdue = await db.execute(
            base_query.where(Vocabulary.next_review < now)
            .order_by(Vocabulary.next_review.asc())
        )
        overdue_words = overdue.scalars().all()
        
        # Категорія 2: NEW (next_review IS NULL)
        new_q = await db.execute(
            base_query.where(Vocabulary.next_review.is_(None))
            .order_by(func.random())
        )
        new_words = new_q.scalars().all()
        
        # Категорія 3: FUTURE (next_review > now) з study_view_count > 0
        future_reviewed = await db.execute(
            base_query.where(
                Vocabulary.next_review > now,
                Vocabulary.study_view_count > 0
            )
            .order_by(Vocabulary.study_view_count.desc())
        )
        future_reviewed_words = future_reviewed.scalars().all()
        
        # ===== ЛОГІКА ПРІОРИТЕТІВ =====
        # Якщо є OVERDUE - показуємо їх + нові
        if overdue_words:
            # Сортуємо NEW за study_view_count (який вже переглядав в Study, той першим)
            new_words_sorted = sorted(new_words, key=lambda w: w.study_view_count, reverse=True)
            words = overdue_words + new_words_sorted
        
        # Якщо OVERDUE немає, але є NEW - показуємо нові + future_reviewed
        elif new_words:
            # Сортуємо NEW за study_view_count
            new_words_sorted = sorted(new_words, key=lambda w: w.study_view_count, reverse=True)
            words = new_words_sorted + future_reviewed_words
        
        # Fallback: якщо немає ні OVERDUE ні NEW - показуємо future_reviewed
        else:
            words = future_reviewed_words
    
    # Застосуємо limit/offset
    words = words[offset : offset + limit]
    
    cards = []
    target_lang = 'uk' if current_user.interface_language == 'ukr' else 'en'
    
    for w in words:
        trans = w.ua if target_lang == 'uk' else w.en
        ctx_trans = w.ctx_ua if target_lang == 'uk' else w.ctx_en
        
        # Отримуємо аудіо з правильної папки (vocabulary, не texts!)
        audio_de = await get_cached_or_generate_tts(w.display, 'de', current_user.id, db, source='vocabulary', generate=False)
        
        trans_urls = []
        if trans:
            parts = [p.strip() for p in re.split(r'[,;]', trans) if p.strip()]
            for part in parts:
                url = await get_cached_or_generate_tts(part, target_lang, current_user.id, db, source='vocabulary', generate=False)
                if url: trans_urls.append(url)

        card_data = {
            "id": w.id,
            "display": w.display,
            "trans": trans,
            "ctx": w.ctx,
            "ctx_trans": ctx_trans,
            "level": w.level,
            "audio_de_url": audio_de,
            "audio_trans_urls": trans_urls,
            "interval": w.interval,
            "ease_factor": w.ease_factor,
            "next_review": w.next_review,
            "last_reviewed": w.last_reviewed,
        }
        
        # Для Review режиму додаємо інформацію про статус
        if mode == "review":
            card_data["study_view_count"] = w.study_view_count
        
        cards.append(card_data)
        
    return cards

@router.post("/vocab/record_study_views")
async def record_study_views(
    word_ids: list[str],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Записує, що юзер переглядав ці слова в режимі Study.
    Інкрементує study_view_count для кожного слова.
    """
    if not word_ids:
        return {"ok": True, "updated": 0}
    
    # Інкрементуємо study_view_count для всіх слів
    await db.execute(
        update(Vocabulary)
        .where(
            Vocabulary.id.in_(word_ids),
            Vocabulary.user_id == current_user.id
        )
        .values(study_view_count=Vocabulary.study_view_count + 1)
    )
    
    await db.commit()
    return {"ok": True, "updated": len(word_ids)}

@router.post("/vocab/update_progress")
async def update_progress(req: VocabProgressRequest, db: AsyncSession = Depends(get_db)):
    word = await db.get(Vocabulary, req.id)
    if not word: raise HTTPException(404, "Word not found")
    
    interval = word.interval or 1.0
    ease = word.ease_factor or 2.5
    
    if req.rating == 'easy':
        interval = interval * ease * 1.3
        ease += 0.15
    elif req.rating == 'medium':
        interval = interval * (ease - 0.5)
        ease -= 0.15
    elif req.rating == 'hard':
        interval = 1.0
        ease = max(1.3, ease - 0.2)
        
    interval = min(90, max(1, interval))
    next_rev = datetime.utcnow() + timedelta(days=interval)
    
    word.interval = interval
    word.ease_factor = ease
    word.last_reviewed = datetime.utcnow()
    word.next_review = next_rev
    
    await db.commit()
    return {"ok": True}

@router.post("/quick_translate")
async def quick_translate(
    req: QuickTranslateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Check duplicates
    res = await db.execute(select(Vocabulary).where(
        Vocabulary.user_id == current_user.id, 
        Vocabulary.text_id == req.tid, 
        Vocabulary.origin == req.text
    ))
    if res.scalar_one_or_none():
        return {"ok": False, "error_key": "word_exists"}

    # 2. Translate
    word_data = await services.translate_word(req.text, req.ctx, db=db, user_id=current_user.id)
    if not word_data or word_data.get('ua') == 'Error':
        return {"ok": False, "error_key": "translation_failed"}

    # Clean duplicates
    word_data['ua'] = remove_duplicate_parts(word_data.get('ua'))
    word_data['en'] = remove_duplicate_parts(word_data.get('en'))

    # 3. Generate Audio (German) - озвучуємо оброблене слово від Gemini
    if not await get_cached_or_generate_tts(word_data['display'], 'de', current_user.id, db, source='vocabulary', log_stats=True):
        return {"ok": False, "error_key": "audio_failed"}

    # 3.1 Generate Audio (Translation) - тільки на мові інтерфейсу
    target_lang = 'uk' if current_user.interface_language == 'ukr' else 'en'
    trans_text = word_data.get('ua') if target_lang == 'uk' else word_data.get('en')
    
    if trans_text:
        parts = [p.strip() for p in re.split(r'[,;]', trans_text) if p.strip()]
        for part in parts:
            if not await get_cached_or_generate_tts(part, target_lang, current_user.id, db, source='vocabulary', log_stats=True):
                return {"ok": False, "error_key": "audio_failed"}
    
    # 4. Record costs (LLM + TTS)
    from ..cost_calculation import record_quick_translate_cost
    cost_result = await record_quick_translate_cost(
        user_id=current_user.id,
        word_data=word_data,  # Pass entire word_data with _full_prompt and _full_response
        interface_language=current_user.interface_language,  # Pass user's interface language
        db=db
    )
    
    if cost_result.get("error"):
        print(f"⚠️ Cost calculation error: {cost_result['error']}")
        # Continue anyway - don't fail translation if cost calc fails
    
    # 5. Save
    wid = str(uuid.uuid4())
    
    # Robust indexing logic
    start_index = -1
    if req.start_char_index is not None:
        search_start = max(0, req.start_char_index - 5)
        start_index = req.ctx.find(req.text, search_start)
    
    if start_index == -1:
        start_index = req.ctx.find(req.text)

    end_index = start_index + len(req.text) if start_index != -1 else -1

    new_word = Vocabulary(
        id=wid, user_id=current_user.id, text_id=req.tid, origin=req.text,
        display=word_data['display'], ua=word_data['ua'], en=word_data['en'],
        ctx=req.ctx, sentence_index=req.sent_idx, start_index=start_index, end_index=end_index,
        level=word_data.get('level'), is_favorite=0
    )
    db.add(new_word)
    
    # Deduct energy based on quick_translate cost (LLM + TTS already calculated)
    spending_usd = cost_result.get("total_cost", 0)
    
    if spending_usd > 0:
        energy_result = await deduct_user_energy(db, current_user.id, spending_usd)
        if not energy_result.get("ok"):
            raise HTTPException(
                status_code=402,  # Payment Required
                detail=f"Insufficient energy: {energy_result.get('error')}"
            )
    
    await db.commit()
    
    # Get updated energy status
    billing_result = await db.execute(select(UserBilling).where(UserBilling.user_id == current_user.id))
    user_billing = billing_result.scalar_one_or_none()
    
    return {
        "ok": True,
        "word": {
            "id": wid,
            "origin": req.text,
            "display": word_data['display'],
            "ua": word_data['ua'],
            "en": word_data['en'],
            "ctx": req.ctx,
            "sentence_index": req.sent_idx,
            "start_index": start_index,
            "end_index": end_index,
            "level": word_data.get('level')
        },
        "energy_left": user_billing.energy_left if user_billing else 0,
        "daily_spending": user_billing.daily_spending if user_billing else 0
    }


@router.post("/explain_word")
async def explain_word(
    req: ExplainWordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    word = req.text.strip()
    if not word:
        return {"ok": False, "error_key": "explain_failed"}

    # Explain only one word; this endpoint is intentionally context-free.
    if len(word.split()) != 1:
        return {"ok": False, "error_key": "explain_single_word_only"}

    try:
        start_index = max(0, req.start_char_index)
        end_index = start_index + len(word)

        data = await services.explain_word(word, db=db)

        existing_res = await db.execute(
            select(ExplainedWord).where(
                ExplainedWord.user_id == current_user.id,
                ExplainedWord.text_id == req.tid,
                ExplainedWord.sentence_index == req.sent_idx,
                ExplainedWord.start_index == start_index,
                ExplainedWord.end_index == end_index,
            )
        )
        existing = existing_res.scalar_one_or_none()

        if existing:
            existing.origin = word
            existing.explanation_json = json.dumps(data, ensure_ascii=False)
            explained = existing
        else:
            explained = ExplainedWord(
                id=str(uuid.uuid4()),
                user_id=current_user.id,
                text_id=req.tid,
                origin=word,
                sentence_index=req.sent_idx,
                start_index=start_index,
                end_index=end_index,
                explanation_json=json.dumps(data, ensure_ascii=False),
            )
            db.add(explained)

        await db.commit()

        return {
            "ok": True,
            "explained_word": {
                "id": explained.id,
                "text": explained.origin,
                "sentence_index": explained.sentence_index,
                "start_index": explained.start_index,
                "end_index": explained.end_index,
                "explanation": data,
            },
        }
    except Exception as e:
        print(f"Explain word error: {e}")
        return {"ok": False, "error_key": "explain_failed"}

@router.post("/update_word")
async def update_word(
    req: VocabUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from ..utils_tts import get_cached_or_generate_tts
    
    lang = current_user.interface_language
    target_lang = 'uk' if lang == 'ukr' else 'en'
    
    # 1. Get existing word
    result = await db.execute(select(Vocabulary).where(Vocabulary.id == req.id, Vocabulary.user_id == current_user.id))
    word = result.scalar_one_or_none()
    
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    
    # 2. Update database
    values = {}
    if target_lang == 'uk':
        values['ua'] = req.translation
    else:
        values['en'] = req.translation
    if req.word is not None:
        trimmed_word = req.word.strip()
        if trimmed_word:
            values['display'] = trimmed_word
        
    await db.execute(
        update(Vocabulary)
        .where(Vocabulary.id == req.id, Vocabulary.user_id == current_user.id)
        .values(**values)
    )
    await db.commit()
    
    # 6. Generate audio for new parts and collect ALL audio URLs (old + new)
    total_cost = 0.0
    all_audio_urls = []
    try:
        # Parse all new translation parts (in order)
        trans_parts = [p.strip() for p in req.translation.split(",") if p.strip()]
        
        # For each part, get existing URL or generate new one
        for part in trans_parts:
            url, cost = await get_cached_or_generate_tts(
                part, target_lang, current_user.id, db, 
                source='vocabulary', log_stats=True, return_cost=True
            )
            if url:
                all_audio_urls.append(url)
            total_cost += cost
        
        # Deduct energy if new audio was generated
        if total_cost > 0:
            energy_result = await services.deduct_user_energy(db, current_user.id, total_cost)
            if not energy_result.get("ok"):
                print(f"Warning: Could not deduct energy for updated translation: {energy_result.get('error')}")
    except Exception as audio_error:
        print(f"Warning: Could not generate audio for updated translation: {audio_error}")
        # Continue without failing - word was updated successfully
    
    # 7. Return updated word with all audio URLs
    return {
        "ok": True,
        "audio_trans_urls": all_audio_urls,  # All audio URLs (old + new) for frontend
        "translation": req.translation,
        "word": req.word.strip() if req.word else None,
    }

@router.post("/toggle_fav")
async def toggle_fav(
    req: ToggleFavRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Get word
    result = await db.execute(select(Vocabulary).where(Vocabulary.id == req.id))
    word = result.scalar_one_or_none()
    
    if not word:
        return {"ok": False}
        
    display_val = word.display
    
    # 2. Check global favorites
    q_existing = select(Vocabulary).where(
        Vocabulary.user_id == current_user.id,
        Vocabulary.display == display_val,
        Vocabulary.is_favorite == 1
    )
    res_existing = await db.execute(q_existing)
    existing_fav = res_existing.first()
    
    if existing_fav:
        # Disable ALL favorites for this display
        await db.execute(
            update(Vocabulary)
            .where(Vocabulary.user_id == current_user.id, Vocabulary.display == display_val)
            .values(is_favorite=0)
        )
    else:
        # Enable THIS one
        await db.execute(
            update(Vocabulary)
            .where(Vocabulary.id == req.id)
            .values(is_favorite=1)
        )
            
    await db.commit()
    return {"ok": True}

@router.post("/remove_word")
async def remove_word(
    req: VocabRemoveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if req.from_vocab:
        # Remove from favorites (soft delete from vocab list view)
        await db.execute(
            update(Vocabulary)
            .where(Vocabulary.id == req.id, Vocabulary.user_id == current_user.id)
            .values(is_favorite=0)
        )
        # Clean up garbage (words that are not favorite and not attached to a text)
        await db.execute(
            delete(Vocabulary)
            .where(Vocabulary.id == req.id, Vocabulary.is_favorite == 0, Vocabulary.text_id == None)
        )
    else:
        # Remove from text context
        res = await db.execute(select(Vocabulary.is_favorite).where(Vocabulary.id == req.id))
        is_fav = res.scalar_one_or_none()
        
        if is_fav == 1:
            # Keep in vocab (favorites), but detach from text
            await db.execute(
                update(Vocabulary)
                .where(Vocabulary.id == req.id, Vocabulary.user_id == current_user.id)
                .values(text_id=None)
            )
        else:
            # Delete completely
            await db.execute(
                delete(Vocabulary)
                .where(Vocabulary.id == req.id, Vocabulary.user_id == current_user.id)
            )
        
    await db.commit()
    return {"ok": True}

@router.post("/report_text")
async def report_text(
    request_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Report a text/lesson as problematic.
    The text goes into quarantine and won't appear for this user anymore.
    Admins can review and take action (ignore or delete).
    """
    lesson_id = request_data.get('id')
    
    if not lesson_id:
        raise HTTPException(400, "lesson_id required")
    
    # Check if already reported by this user
    existing = await db.execute(
        select(ReportedLesson).where(
            ReportedLesson.lesson_id == lesson_id,
            ReportedLesson.user_id == current_user.id,
            ReportedLesson.status == 'reported'
        )
    )
    
    if existing.scalar_one_or_none():
        return {"ok": False, "error": "already_reported"}
    
    # Create report
    report = ReportedLesson(
        lesson_id=lesson_id,
        user_id=current_user.id,
        status='reported'
    )
    db.add(report)
    await db.commit()
    
    return {"ok": True}


@router.post("/vocab/add_custom")
async def add_custom_word(
    request: AddCustomWordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a custom word to user's vocabulary (without lesson context)"""
    from ..services import translate_custom_word_async
    
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    
    # Check word count (max 4 words/phrase)
    words = text.split()
    if len(words) > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 words allowed")
    
    try:
        # Use AI to translate and validate
        translation_result = await translate_custom_word_async(text, user_id=current_user.id, db=db)
        
        # If AI validation failed (not German or invalid)
        if translation_result.get("success") == False:
            return {"success": False, "error": translation_result.get("error", "Invalid word or phrase")}
        
        # Extract translation data and cost from result
        translation_data = translation_result
        llm_cost = translation_result.get("llm_cost", 0.0)  # LLM cost from translate_custom_word_async
        
        # Clean duplicates from translations (both UA and EN)
        translation_data['ua'] = remove_duplicate_parts(translation_data.get('ua'))
        translation_data['en'] = remove_duplicate_parts(translation_data.get('en'))
        
        # Create vocabulary entry
        vocab = Vocabulary(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            origin=text,  # Original German word
            display=translation_data.get("display", text),  # Formatted German (with article/plural)
            ua=translation_data.get("ua", ""),  # Ukrainian translation
            en=translation_data.get("en", ""),  # English translation
            level=translation_data.get("level", "A1"),
            ctx=translation_data.get("context", ""),  # Example sentence in German
            ctx_ua=translation_data.get("ua_context", ""),  # Ukrainian translation of context
            ctx_en=translation_data.get("en_context", ""),  # English translation of context
            text_id=request.text_id or None,  # Optional: link to a text
            is_favorite=1  # Custom words are added to favorites by default
        )
        
        db.add(vocab)
        await db.commit()
        
        # Generate audio for the word
        total_tts_cost = 0.0
        try:
            # Always generate German (with return_cost=True to track cost)
            # Use translation_data['display'] which is the German form, not the input text
            audio_de_url, de_cost = await get_cached_or_generate_tts(
                translation_data['display'], "de", current_user.id, db, source='vocabulary', 
                log_stats=True, return_cost=True
            )
            total_tts_cost += de_cost
            
            # Generate translation audio only for interface language
            target_lang = 'uk' if current_user.interface_language == 'ukr' else 'en'
            trans_text = translation_data.get('ua') if target_lang == 'uk' else translation_data.get('en')
            
            audio_trans_urls = []
            if trans_text:
                trans_parts = trans_text.split(",")
                for part in trans_parts:
                    url, trans_cost = await get_cached_or_generate_tts(
                        part.strip(), target_lang, current_user.id, db, 
                        source='vocabulary', log_stats=True, return_cost=True
                    )
                    total_tts_cost += trans_cost
                    if url:
                        audio_trans_urls.append(url)
            
            # Note: Audio URLs are not stored in vocabulary table
            # They are generated on-demand when user clicks play (like in lesson view)
            
            await db.commit()
        except Exception as audio_error:
            print(f"Warning: Could not generate audio for custom word: {audio_error}")
            # Continue without audio - it's not critical
        
        # Deduct energy from user for BOTH LLM and TTS costs
        total_cost = llm_cost + total_tts_cost
        if total_cost > 0:
            energy_result = await services.deduct_user_energy(db, current_user.id, total_cost)
            if not energy_result.get("ok"):
                print(f"Warning: Could not deduct energy for custom word: {energy_result.get('error')}")
                # Don't fail the request - the word was created successfully
        else:
            print(f"DEBUG: No cost to deduct (llm_cost={llm_cost}, tts_cost={total_tts_cost})")
        
        return {"success": True, "word_id": vocab.id}
        
    except Exception as e:
        print(f"Error adding custom word: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing word: {str(e)}")


@router.post("/vocab/generate_audio")
async def generate_audio(
    request: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate audio for text on demand (when user plays audio)
    Request body: {"text": "...", "lang": "de|uk|en"}
    Returns: {"url": "...audio path..."}
    
    Process:
    1. Generate audio (with caching - if exists in cache, returns path without regenerating)
    2. If generated (not cached): Record TTS cost, deduct energy from user
    3. Return audio URL to frontend
    """
    from ..utils_tts import get_cached_or_generate_tts
    
    text = request.get("text", "").strip()
    lang = request.get("lang", "de")  # de, uk, en
    
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    
    if lang not in ['de', 'uk', 'en']:
        raise HTTPException(status_code=400, detail="Language must be de, uk, or en")
    
    try:
        # Generate audio and get cost (with caching - if exists in cache, returns path without regenerating)
        audio_url, tts_cost = await get_cached_or_generate_tts(
            text, 
            lang, 
            current_user.id, 
            db, 
            source='vocabulary',
            log_stats=True,
            return_cost=True  # Returns tuple (url, cost)
        )
        
        # If audio was generated (cost > 0), deduct energy from UserBilling
        if tts_cost > 0:
            energy_result = await services.deduct_user_energy(db, current_user.id, tts_cost)
            if not energy_result.get("ok"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not deduct energy: {energy_result.get('error')}"
                )
        
        return {"url": audio_url}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating audio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating audio: {str(e)}")
