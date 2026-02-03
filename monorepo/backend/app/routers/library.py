import json
import uuid
import math
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from ..database import get_db
from ..models import User, Text, Lesson, UserLesson, LessonAudio, Vocabulary, QuizResult
from ..schemas import TextGenerateRequest, TextReadSchema, ToggleFavRequest, QuizResultRequest, VocabWordSchema
from ..dependencies import get_current_user
from .. import services, cost_calculation
from ..services import deduct_user_energy
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

    # Generation (pass db to get model from AI preferences)
    # Now returns tuple: (data, prompt, raw_response, model_id)
    data, prompt_text, raw_response_text, model_id = await services.generate_german_text(
        req.topic, count, req.level, req.style, db=db
    )
    
    # Record cost for text generation
    # Start with a reasonable default
    energy_left = 100
    
    if data.get('sentences') and raw_response_text:
        cost_result = await cost_calculation.record_text_generation_cost(
            user_id=current_user.id,
            prompt_text=prompt_text,
            response_text=raw_response_text,
            model_id=model_id,
            db=db
        )
        
        spending_usd = cost_result.get("total_cost", 0)
        
        # Deduct energy based on actual spending
        if spending_usd > 0:
            energy_result = await deduct_user_energy(db, current_user.id, spending_usd)
            if not energy_result.get("ok"):
                raise HTTPException(
                    status_code=402,  # Payment Required
                    detail=f"Insufficient energy: {energy_result.get('error')}"
                )
            energy_left = energy_result.get("energy_left", 0)
    
    title_json = json.dumps({'de': data.get('title_de', req.topic), 'ukr': data.get('title_ua'), 'eng': data.get('title_en')}, ensure_ascii=False)
    tid = str(uuid.uuid4())
    
    # Save to global Lesson table (anonymous, not user-specific)
    new_lesson = Lesson(
        id=tid,
        title=title_json,
        level=req.level,
        content_json=json.dumps(data.get('sentences', []), ensure_ascii=False),
        quiz_json=json.dumps(data.get('quiz', []), ensure_ascii=False),
        audio_status='pending'
    )
    db.add(new_lesson)
    
    # Create UserLesson entry to track that this user has access to this lesson
    user_lesson = UserLesson(
        user_id=current_user.id,
        lesson_id=tid,
        is_favorite=0
    )
    db.add(user_lesson)
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
    
    return {"id": tid, "energy_left": energy_left}

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
        failed = 0
        
        # Отримуємо ID уроку з останнього створеного уроку користувача
        # (Це не ідеально, але працює для фонової генерації)
        lesson_result = await db.execute(
            select(Lesson).join(
                UserLesson,
                UserLesson.lesson_id == Lesson.id
            ).where(UserLesson.user_id == user_id).order_by(Lesson.created_at.desc()).limit(1)
        )
        lesson = lesson_result.scalar_one_or_none()
        
        if not lesson:
            print(f"❌ Could not find lesson for user {user_id}")
            return
        
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
                        db,
                        source='texts',  # Аудіо для речень у текстах
                        deduct_credits=False  # Кредити вже списані при створенні тексту
                    )
                except Exception as e:
                    print(f"⚠️ Error generating audio for sentence {idx} (attempt {retry_count + 1}): {e}")
                    retry_count += 1
                    if retry_count > max_retries:
                        break
                    await asyncio.sleep(0.5)
            
            # Записуємо результат в lesson_audio таблицю
            if audio_url:
                # Витягуємо шлях від URL (наприклад /static/audio/cache/de/ab/hash.ogg -> cache/de/ab/hash.ogg)
                audio_path = audio_url.replace('/static/audio/', '') if audio_url.startswith('/static/audio/') else audio_url
                
                # Перевіряємо чи запис вже існує
                existing = await db.execute(
                    select(LessonAudio).where(
                        and_(
                            LessonAudio.lesson_id == lesson.id,
                            LessonAudio.sentence_index == idx,
                            LessonAudio.lang == lang
                        )
                    )
                )
                lesson_audio = existing.scalar_one_or_none()
                
                if lesson_audio:
                    # Оновлюємо існуючий запис
                    lesson_audio.audio_path = audio_path
                    lesson_audio.status = 'generated'
                    lesson_audio.generated_at = func.now()
                else:
                    # Створюємо новий запис
                    lesson_audio = LessonAudio(
                        lesson_id=lesson.id,
                        sentence_index=idx,
                        lang=lang,
                        audio_path=audio_path,
                        status='generated',
                        generated_at=func.now()
                    )
                    db.add(lesson_audio)
                
                completed += 1
            else:
                failed += 1
                # Записуємо невдалу спробу
                existing = await db.execute(
                    select(LessonAudio).where(
                        and_(
                            LessonAudio.lesson_id == lesson.id,
                            LessonAudio.sentence_index == idx,
                            LessonAudio.lang == lang
                        )
                    )
                )
                lesson_audio = existing.scalar_one_or_none()
                
                if not lesson_audio:
                    lesson_audio = LessonAudio(
                        lesson_id=lesson.id,
                        sentence_index=idx,
                        lang=lang,
                        status='failed'
                    )
                    db.add(lesson_audio)
        
        # Оновлюємо статус уроку
        if failed == 0:
            lesson.audio_status = 'completed'
        else:
            lesson.audio_status = 'partial_failed'
        
        await db.commit()
        print(f"✅ Background audio generation completed: {completed}/{len(sentences)} sentences (failed: {failed})")
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
    sort: str = "date_desc",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Query: Join UserLesson (user's lessons) with Lesson (lesson content)
    from sqlalchemy import and_
    
    query = select(Lesson).join(
        UserLesson,
        UserLesson.lesson_id == Lesson.id
    ).where(UserLesson.user_id == current_user.id)
    
    count_query = select(func.count()).select_from(Lesson).join(
        UserLesson,
        UserLesson.lesson_id == Lesson.id
    ).where(UserLesson.user_id == current_user.id)

    if fav:
        query = query.where(UserLesson.is_favorite == 1)
        count_query = count_query.where(UserLesson.is_favorite == 1)

    if levels:
        level_list = [lvl for lvl in levels.split(',') if lvl in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']]
        if level_list:
            query = query.where(Lesson.level.in_(level_list))
            count_query = count_query.where(Lesson.level.in_(level_list))

    if search:
        search_pattern = f"%{search}%"
        query = query.where(Lesson.title.like(search_pattern))
        count_query = count_query.where(Lesson.title.like(search_pattern))

    total_count_res = await db.execute(count_query)
    total_count = total_count_res.scalar_one()

    # Apply sorting
    if sort == "date_asc":
        query = query.order_by(Lesson.created_at.asc())
    else:  # default: date_desc
        query = query.order_by(Lesson.created_at.desc())
    
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    lessons = result.scalars().all()
    
    text_models = []
    for lesson in lessons:
        # Convert Lesson to TextReadSchema format for backward compatibility
        tm = TextReadSchema(
            id=lesson.id,
            user_id=current_user.id,  # Anonymous lesson, set to current user
            title=lesson.title,
            level=lesson.level,
            content_json=lesson.content_json,
            quiz_json=lesson.quiz_json,
            is_favorite=0  # Will be set from UserLesson below
        )
        try:
            titles = json.loads(lesson.title) if lesson.title else {}
            lang_key = current_user.interface_language
            tm.display_title = titles.get('de', lesson.title)
            tm.trans_title = titles.get(lang_key, '')
        except (json.JSONDecodeError, TypeError):
            tm.display_title = lesson.title
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
    
    # Try to delete as lesson first (new global lessons)
    lesson_result = await db.execute(select(Lesson).where(Lesson.id == text_id))
    lesson = lesson_result.scalar_one_or_none()
    
    if lesson:
        # Verify user created this lesson or is just removing it from their library
        user_lesson = await db.execute(
            select(UserLesson).where(
                and_(UserLesson.user_id == current_user.id, UserLesson.lesson_id == text_id)
            )
        )
        ul = user_lesson.scalar_one_or_none()
        
        if not ul:
            raise HTTPException(status_code=404, detail="Lesson not found")
        
        # 1. Видаляємо entry з user_lessons (видаляємо з бібліотеки користувача)
        # Не видаляємо сам Lesson, щоб інші користувачі могли його переглядати
        await db.delete(ul)
        
        # 2. Видаляємо результати квізу ДЛЯ ЦЬОГО КОРИСТУВАЧА
        quiz_results = (await db.execute(
            select(QuizResult).where(
                QuizResult.user_id == current_user.id,
                QuizResult.lesson_id == text_id
            )
        )).scalars().all()
        
        for result in quiz_results:
            await db.delete(result)
        
        # 3. Видаляємо слова це привязані ТІЛЬКИ до цього уроку (is_favorite=0)
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
                vocab.text_id = None
        
        await db.commit()
        return {"ok": True}
    
    # Fallback: delete as old Text (user-specific)
    text_result = await db.execute(select(Text).where(Text.id == text_id))
    text = text_result.scalar_one_or_none()
    
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
    quiz_results = (await db.execute(
        select(QuizResult).where(
            QuizResult.text_id == text_id,
            QuizResult.user_id == current_user.id
        )
    )).scalars().all()
    
    for result in quiz_results:
        await db.delete(result)
    
    # 3. Видаляємо слова що привязані ТІЛЬКИ до цього тексту (is_favorite=0)
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
            vocab.text_id = None
    
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
    # Try to toggle favorite for lesson first
    user_lesson = await db.execute(
        select(UserLesson).where(
            and_(UserLesson.user_id == current_user.id, UserLesson.lesson_id == req.id)
        )
    )
    ul = user_lesson.scalar_one_or_none()
    
    if ul:
        ul.is_favorite = 1 - ul.is_favorite
    else:
        # Fallback to old Text table
        text = await db.get(Text, req.id)
        if text and text.user_id == current_user.id:
            text.is_favorite = 1 - text.is_favorite
    
    await db.commit()
    return {"ok": True}

@router.get("/texts/{text_id}")
async def get_text(text_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # First try to get from Lesson (new global lessons)
    lesson_result = await db.execute(select(Lesson).where(Lesson.id == text_id))
    lesson = lesson_result.scalar_one_or_none()
    
    # Verify user has access to this lesson
    if lesson:
        user_lesson = await db.execute(
            select(UserLesson).where(
                and_(UserLesson.user_id == current_user.id, UserLesson.lesson_id == text_id)
            )
        )
        if not user_lesson.scalar_one_or_none():
            raise HTTPException(404, "Lesson not found")
        
        # Convert Lesson to TextReadSchema format
        text_model = TextReadSchema(
            id=lesson.id,
            user_id=current_user.id,  # Anonymous lesson, set to current user
            title=lesson.title,
            level=lesson.level,
            content_json=lesson.content_json,
            quiz_json=lesson.quiz_json,
            is_favorite=0
        )
    else:
        # Fallback to old Text table for backward compatibility
        text_result = await db.execute(select(Text).where(Text.id == text_id))
        text = text_result.scalar_one_or_none()
        
        if not text or text.user_id != current_user.id:
            raise HTTPException(404, "Text not found")
        
        text_model = TextReadSchema.model_validate(text)
        # Use text.id for vocab queries
        text_id_for_vocab = text.id
    
    # Fetch vocab for this text to highlight
    vocab_res = await db.execute(select(Vocabulary).where(Vocabulary.text_id == text_id, Vocabulary.user_id == current_user.id))
    vocab = vocab_res.scalars().all()
    
    vocab_models = [VocabWordSchema.model_validate(v) for v in vocab]

    # Fetch last quiz result (now can come from either text_id or lesson_id)
    q_res = await db.execute(select(QuizResult).where(
        QuizResult.user_id == current_user.id
    ).where(
        (QuizResult.text_id == text_id) | (QuizResult.lesson_id == text_id)
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
    # Support both text_id and lesson_id for backward compatibility
    # Try to determine if this is a lesson or text
    lesson = None
    text = None
    
    if req.text_id:
        # Check if it's a lesson
        lesson_result = await db.execute(select(Lesson).where(Lesson.id == req.text_id))
        lesson = lesson_result.scalar_one_or_none()
        
        if not lesson:
            # Try as text
            text_result = await db.execute(select(Text).where(Text.id == req.text_id))
            text = text_result.scalar_one_or_none()
    
    # Check if result exists
    q_res = await db.execute(select(QuizResult).where(
        QuizResult.user_id == current_user.id,
        (QuizResult.text_id == req.text_id) | (QuizResult.lesson_id == req.text_id)
    ))
    existing = q_res.scalar_one_or_none()
    
    if existing:
        existing.score = req.score
        existing.total_questions = req.total
        existing.created_at = func.now()
    else:
        # Determine whether to save as lesson_id or text_id
        new_result = QuizResult(user_id=current_user.id, score=req.score, total_questions=req.total)
        if lesson:
            new_result.lesson_id = req.text_id
        else:
            new_result.text_id = req.text_id
        db.add(new_result)
        
    await db.commit()
    return {"ok": True}