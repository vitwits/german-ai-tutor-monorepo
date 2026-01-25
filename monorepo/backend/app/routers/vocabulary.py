import uuid
import re
import math
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, update, delete

from ..database import get_db
from ..models import User, Vocabulary, UserFavoriteSentence, Sentence
from ..schemas import VocabUpdateRequest, VocabRemoveRequest, ToggleFavRequest, VocabProgressRequest, QuickTranslateRequest
from ..dependencies import get_current_user
from .. import services, billing
from ..utils_tts import get_cached_or_generate_tts

router = APIRouter(prefix="/api", tags=["vocabulary"])

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

        return {"items": words, "total": total, "pages": math.ceil(total / per_page)}

@router.get("/vocab/session")
async def vocab_session(
    levels: str = None,
    limit: int = 50,
    q: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(Vocabulary).where(Vocabulary.user_id == current_user.id)
    
    if levels:
        lvl_list = [l for l in levels.split(',') if l]
        if lvl_list: query = query.where(Vocabulary.level.in_(lvl_list))
    
    # Сортування: спочатку прострочені (next_review < now), потім нові (next_review NULL)
    query = query.order_by(
        func.coalesce(Vocabulary.next_review, datetime.utcnow()).asc()
    ).limit(limit)
    
    result = await db.execute(query)
    words = result.scalars().all()
    
    cards = []
    target_lang = 'uk' if current_user.interface_language == 'ukr' else 'en'
    
    for w in words:
        trans = w.ua if target_lang == 'uk' else w.en
        
        # Отримуємо аудіо (тільки з кешу, generate=False)
        audio_de = await get_cached_or_generate_tts(w.display, 'de', current_user.id, db, generate=False)
        
        trans_urls = []
        if trans:
            parts = [p.strip() for p in re.split(r'[,;]', trans) if p.strip()]
            for part in parts:
                url = await get_cached_or_generate_tts(part, target_lang, current_user.id, db, generate=False)
                if url: trans_urls.append(url)

        cards.append({
            "id": w.id,
            "display": w.display,
            "trans": trans,
            "ctx": w.ctx,
            "level": w.level,
            "audio_de_url": audio_de,
            "audio_trans_urls": trans_urls
        })
        
    return cards

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

    # 3. Generate Audio (Async)
    await get_cached_or_generate_tts(req.text, 'de', current_user.id, db, log_stats=True)
    
    # 4. Save
    wid = str(uuid.uuid4())
    # Simple find for index (can be improved)
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