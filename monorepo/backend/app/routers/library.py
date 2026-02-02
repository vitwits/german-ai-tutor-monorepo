import json
import uuid
import math
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..database import get_db
from ..models import User, Text, Vocabulary, QuizResult
from ..schemas import TextGenerateRequest, TextReadSchema, ToggleFavRequest, QuizResultRequest, VocabWordSchema
from ..dependencies import get_current_user
from .. import services, billing, cost_calculation
from ..utils_tts import delete_sentence_audio_cache

router = APIRouter(prefix="/api", tags=["library"])

@router.post("/generate", response_model=dict)
async def generate_text_endpoint(
    req: TextGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Map: Level -> Size -> Count
    sentence_map = {
        'A1': {'S': 5, 'M': 8, 'L': 12}, 'A2': {'S': 6, 'M': 8, 'L': 11},
        'B1': {'S': 5, 'M': 7, 'L': 10}, 'B2': {'S': 5, 'M': 7, 'L': 10},
        'C1': {'S': 6, 'M': 8, 'L': 9}, 'C2': {'S': 6, 'M': 7, 'L': 8}
    }
    count = sentence_map.get(req.level, sentence_map['A2']).get(req.size, 8)

    # Billing
    new_bal = await billing.deduct_credits(current_user.id, billing.PRICING['lesson_generation'])
    
    # Generation (pass db to get model from AI preferences)
    # Now returns tuple: (data, prompt, raw_response, model_id)
    data, prompt_text, raw_response_text, model_id = await services.generate_german_text(
        req.topic, count, req.level, req.style, db=db
    )
    
    # Record cost for text generation
    if data.get('sentences') and raw_response_text:
        await cost_calculation.record_text_generation_cost(
            user_id=current_user.id,
            prompt_text=prompt_text,
            response_text=raw_response_text,
            model_id=model_id,
            db=db
        )
    
    title_json = json.dumps({'de': data.get('title_de', req.topic), 'ukr': data.get('title_ua'), 'eng': data.get('title_en')}, ensure_ascii=False)
    tid = str(uuid.uuid4())
    
    new_text = Text(
        id=tid,
        user_id=current_user.id,
        title=title_json,
        level=req.level,
        content_json=json.dumps(data.get('sentences', []), ensure_ascii=False),
        quiz_json=json.dumps(data.get('quiz', []), ensure_ascii=False)
    )
    db.add(new_text)
    await db.commit()
    
    # Запускаємо batch генерацію аудіо в фоні (не чекаємо завершення)
    # Отримуємо sentences з даних
    sentences_list = data.get('sentences', [])
    if sentences_list:
        sentence_texts = [s.get('de', '') for s in sentences_list if s.get('de')]
        # Запускаємо як background task
        asyncio.create_task(
            _generate_audio_batch_background(
                user_id=current_user.id,
                sentences=sentence_texts,
                lang='de',
                db=db
            )
        )
    
    return {"id": tid, "credits": new_bal}

async def _generate_audio_batch_background(user_id: str, sentences: list, lang: str, db: AsyncSession):
    """Фонова функція для генерації аудіо після створення тексту"""
    try:
        from .tts import generate_audio_batch_endpoint
        from ..schemas import TTSBatchRequest
        
        req = TTSBatchRequest(sentences=sentences, lang=lang)
        
        # Імітуємо виклик endpoint'а в фоні
        from fastapi.requests import Request
        # Просто викликаємо логіку батч генерації
        completed = 0
        for idx, sentence_text in enumerate(sentences):
            if not sentence_text or not sentence_text.strip():
                continue
            
            audio_url = None
            retry_count = 0
            max_retries = 2
            
            while retry_count <= max_retries and not audio_url:
                try:
                    from ..utils_tts import get_cached_or_generate_tts
                    audio_url = await get_cached_or_generate_tts(
                        sentence_text,
                        lang,
                        user_id,
                        db
                    )
                except Exception as e:
                    print(f"⚠️ Error generating audio for sentence {idx} (attempt {retry_count + 1}): {e}")
                    retry_count += 1
                    if retry_count > max_retries:
                        break
                    await asyncio.sleep(0.5)
            
            if audio_url:
                completed += 1
        
        print(f"✅ Background audio generation completed: {completed}/{len(sentences)} sentences")
    except Exception as e:
        print(f"❌ Error in background audio generation: {e}")
        import traceback
        traceback.print_exc()

@router.get("/library", response_model=dict)
async def get_library(
    page: int = 1,
    per_page: int = 18,
    fav: bool = False,
    levels: str = None,
    search: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(Text).where(Text.user_id == current_user.id)
    count_query = select(func.count()).select_from(Text).where(Text.user_id == current_user.id)

    if fav:
        query = query.where(Text.is_favorite == 1)
        count_query = count_query.where(Text.is_favorite == 1)

    if levels:
        level_list = [lvl for lvl in levels.split(',') if lvl in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']]
        if level_list:
            query = query.where(Text.level.in_(level_list))
            count_query = count_query.where(Text.level.in_(level_list))

    if search:
        search_pattern = f"%{search}%"
        query = query.where(Text.title.like(search_pattern))
        count_query = count_query.where(Text.title.like(search_pattern))

    total_count_res = await db.execute(count_query)
    total_count = total_count_res.scalar_one()

    query = query.order_by(Text.id.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    texts = result.scalars().all()
    
    text_models = []
    for t in texts:
        tm = TextReadSchema.model_validate(t)
        try:
            titles = json.loads(t.title) if t.title else {}
            lang_key = current_user.interface_language
            tm.display_title = titles.get('de', t.title)
            tm.trans_title = titles.get(lang_key, '')
        except (json.JSONDecodeError, TypeError):
            tm.display_title = t.title
            tm.trans_title = ""
        text_models.append(tm)

    return {
        "texts": text_models,
        "page": page,
        "total_pages": math.ceil(total_count / per_page),
        "total_count": total_count
    }

@router.post("/delete_text")
async def delete_text(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    text_id = payload.get("id")
    # Use select instead of get for better reliability with aiosqlite
    result = await db.execute(select(Text).where(Text.id == text_id))
    text = result.scalar_one_or_none()
    
    if not text or text.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Text not found")
    
    # 1. Видаляємо кеш аудіо для всіх речень цього тексту
    try:
        sentences = json.loads(text.content_json) if text.content_json else []
        for sentence in sentences:
            sentence_text = sentence.get('de', '')
            if sentence_text:
                delete_sentence_audio_cache(sentence_text, lang='de')
    except Exception as e:
        print(f"Error deleting sentence audio cache: {e}")
    
    # 2. Видаляємо результати квізу для цього тексту
    await db.execute(
        select(QuizResult).where(
            QuizResult.text_id == text_id,
            QuizResult.user_id == current_user.id
        )
    )
    quiz_results = (await db.execute(
        select(QuizResult).where(
            QuizResult.text_id == text_id,
            QuizResult.user_id == current_user.id
        )
    )).scalars().all()
    
    for result in quiz_results:
        await db.delete(result)
    
    # 3. Видаляємо слова що привязані ТІЛЬКИ до цього тексту (is_favorite=0)
    # Слова з is_favorite=1 залишаються, але text_id стає NULL
    vocab_items = (await db.execute(
        select(Vocabulary).where(
            Vocabulary.text_id == text_id,
            Vocabulary.user_id == current_user.id
        )
    )).scalars().all()
    
    for vocab in vocab_items:
        if vocab.is_favorite == 0:
            await db.delete(vocab)
        else:
            vocab.text_id = None  # Зберігаємо улюблене слово, але без прив'язки до тексту
    
    # 4. Видаляємо сам текст
    await db.delete(text)
    await db.commit()
    return {"ok": True}

@router.post("/toggle_text_fav")
async def toggle_text_fav(
    req: ToggleFavRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    text = await db.get(Text, req.id)
    if text and text.user_id == current_user.id:
        text.is_favorite = 1 - text.is_favorite
        await db.commit()
    return {"ok": True}

@router.get("/texts/{text_id}")
async def get_text(text_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Use select instead of get for better reliability with aiosqlite
    result = await db.execute(select(Text).where(Text.id == text_id))
    text = result.scalar_one_or_none()
    
    if not text or text.user_id != current_user.id:
        raise HTTPException(404, "Text not found")
    
    # Fetch vocab for this text to highlight
    vocab_res = await db.execute(select(Vocabulary).where(Vocabulary.text_id == text_id, Vocabulary.user_id == current_user.id))
    vocab = vocab_res.scalars().all()
    
    text_model = TextReadSchema.model_validate(text)
    vocab_models = [VocabWordSchema.model_validate(v) for v in vocab]

    # Fetch last quiz result
    q_res = await db.execute(select(QuizResult).where(
        QuizResult.user_id == current_user.id,
        QuizResult.text_id == text_id
    ).order_by(QuizResult.created_at.desc()).limit(1))
    last_result = q_res.scalar_one_or_none()
    
    last_result_data = None
    if last_result:
        last_result_data = {"score": last_result.score, "total_questions": last_result.total_questions}
    
    return {"text": text_model, "vocab": vocab_models, "last_quiz_result": last_result_data}

@router.post("/save_quiz_result")
async def save_quiz_result(
    req: QuizResultRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if result exists
    q_res = await db.execute(select(QuizResult).where(
        QuizResult.user_id == current_user.id,
        QuizResult.text_id == req.text_id
    ))
    existing = q_res.scalar_one_or_none()
    
    if existing:
        existing.score = req.score
        existing.total_questions = req.total
        existing.created_at = func.now()
    else:
        new_result = QuizResult(user_id=current_user.id, text_id=req.text_id, score=req.score, total_questions=req.total)
        db.add(new_result)
        
    await db.commit()
    return {"ok": True}