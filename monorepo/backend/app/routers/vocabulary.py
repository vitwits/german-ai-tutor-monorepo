import uuid
import re
import math
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, update, delete

from ..database import get_db
from ..models import User, Vocabulary, UserFavoriteSentence, Sentence
from ..schemas import VocabUpdateRequest, VocabRemoveRequest, ToggleFavRequest, VocabProgressRequest, QuickTranslateRequest, VocabWordSchema
from ..dependencies import get_current_user
from .. import services, billing
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
            .where(UserFavoriteSentence.user_id == current_user.id)\
            .order_by(UserFavoriteSentence.created_at.desc())\
            .offset(offset).limit(per_page)
            
        count_query = select(func.count()).select_from(UserFavoriteSentence).where(UserFavoriteSentence.user_id == current_user.id)
        
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
        result = await db.execute(query.order_by(Vocabulary.id.desc()).offset(offset).limit(per_page))
        words = result.scalars().all()
        
        # Transform to dicts and add display_trans
        items_data = []
        target_lang = 'uk' if current_user.interface_language == 'ukr' else 'en'
        
        for w in words:
            # Convert SQLAlchemy model to dict (or construct manually to be safe)
            item = VocabWordSchema.model_validate(w)
            # Add computed field
            item.display_trans = w.ua if target_lang == 'uk' else w.en
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
        
        # Розділяємо NEW на FREQUENT (study_view_count >= 3) та INFREQUENT
        new_frequent = [w for w in new_words if w.study_view_count >= 3]
        new_infrequent = [w for w in new_words if w.study_view_count < 3]
        
        # Категорія 3: FUTURE (next_review > now)
        future = await db.execute(
            base_query.where(Vocabulary.next_review > now)
            .order_by(func.random())
        )
        future_words = future.scalars().all()
        
        # Розділяємо FUTURE на FREQUENT (study_view_count >= 5) та INFREQUENT
        future_frequent = [w for w in future_words if w.study_view_count >= 5]
        # future_infrequent = [w for w in future_words if w.study_view_count < 5]
        
        # Об'єднуємо по пріоритетам:
        # 1. OVERDUE (ваговий коефіцієнт 10)
        # 2. NEW + FREQUENT (вага 8)
        # 3. NEW + INFREQUENT (вага 5)
        # 4. FUTURE + FREQUENT (вага 3)
        
        words = (
            overdue_words +
            new_frequent +
            new_infrequent +
            future_frequent
        )
    
    # Застосуємо limit/offset
    words = words[offset : offset + limit]
    
    cards = []
    target_lang = 'uk' if current_user.interface_language == 'ukr' else 'en'
    
    for w in words:
        trans = w.ua if target_lang == 'uk' else w.en
        
        # Отримуємо аудіо (тільки з кешу)
        audio_de = await get_cached_or_generate_tts(w.display, 'de', current_user.id, db, generate=False)
        
        trans_urls = []
        if trans:
            parts = [p.strip() for p in re.split(r'[,;]', trans) if p.strip()]
            for part in parts:
                url = await get_cached_or_generate_tts(part, target_lang, current_user.id, db, generate=False)
                if url: trans_urls.append(url)

        card_data = {
            "id": w.id,
            "display": w.display,
            "trans": trans,
            "ctx": w.ctx,
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
    word_data = services.translate_word(req.text, req.ctx)
    if not word_data or word_data.get('ua') == 'Error':
        return {"ok": False, "error_key": "translation_failed"}

    # Clean duplicates
    word_data['ua'] = remove_duplicate_parts(word_data.get('ua'))
    word_data['en'] = remove_duplicate_parts(word_data.get('en'))

    # 3. Generate Audio (German) - озвучуємо оброблене слово від Gemini, а не оригінал!
    if not await get_cached_or_generate_tts(word_data['display'], 'de', current_user.id, db, log_stats=True):
        return {"ok": False, "error_key": "audio_failed"}

    # 3.1 Generate Audio (Ukrainian) - розбиваємо на частини
    uk_text = word_data.get('ua')
    if uk_text:
        parts = [p.strip() for p in re.split(r'[,;]', uk_text) if p.strip()]
        for part in parts:
            if not await get_cached_or_generate_tts(part, 'uk', current_user.id, db, log_stats=True):
                return {"ok": False, "error_key": "audio_failed"}
    
    # 3.2 Generate Audio (English) - розбиваємо на частини
    en_text = word_data.get('en')
    if en_text:
        parts = [p.strip() for p in re.split(r'[,;]', en_text) if p.strip()]
        for part in parts:
            if not await get_cached_or_generate_tts(part, 'en', current_user.id, db, log_stats=True):
                return {"ok": False, "error_key": "audio_failed"}
    
    # 4. Save
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
    
    cost = billing.calculate_translation_cost(req.text)
    await billing.deduct_credits(current_user.id, cost)
    
    await db.commit()
    return {"ok": True}

@router.post("/update_word")
async def update_word(
    req: VocabUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lang = current_user.interface_language
    
    values = {}
    if lang == 'ukr':
        values['ua'] = req.translation
    else:
        values['en'] = req.translation
        
    await db.execute(
        update(Vocabulary)
        .where(Vocabulary.id == req.id, Vocabulary.user_id == current_user.id)
        .values(**values)
    )
    await db.commit()
    return {"ok": True}

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