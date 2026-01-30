import json
import uuid
import math
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..database import get_db
from ..models import User, Text, Vocabulary, GrammarExplanation, QuizResult
from ..schemas import TextGenerateRequest, TextReadSchema, ToggleFavRequest, GrammarExplainRequest, QuizResultRequest, VocabWordSchema
from ..dependencies import get_current_user
from .. import services, billing
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
    data = await services.generate_german_text(req.topic, count, req.level, req.style, db=db)
    
    title_json = json.dumps({'de': data.get('title_de', req.topic), 'ukr': data.get('title_ua'), 'eng': data.get('title_en')})
    tid = str(uuid.uuid4())
    
    new_text = Text(
        id=tid,
        user_id=current_user.id,
        title=title_json,
        level=req.level,
        content_json=json.dumps(data.get('sentences', [])),
        quiz_json=json.dumps(data.get('quiz', []))
    )
    db.add(new_text)
    await db.commit()
    
    return {"id": tid, "credits": new_bal}

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
    
    # 3. Видаляємо пояснення граматики для цього тексту
    await db.execute(
        select(GrammarExplanation).where(
            GrammarExplanation.text_id == text_id
        )
    )
    grammar_exps = (await db.execute(
        select(GrammarExplanation).where(
            GrammarExplanation.text_id == text_id
        )
    )).scalars().all()
    
    for exp in grammar_exps:
        await db.delete(exp)
    
    # 4. Видаляємо слова що привязані ТІЛЬКИ до цього тексту (is_favorite=0)
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
    
    # 5. Видаляємо сам текст
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

@router.post("/explain_grammar")
async def explain_grammar(
    req: GrammarExplainRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check cache
    if req.text_id and req.sentence_index is not None:
        res = await db.execute(select(GrammarExplanation).where(
            GrammarExplanation.text_id == req.text_id,
            GrammarExplanation.sentence_index == req.sentence_index,
            GrammarExplanation.language == current_user.interface_language
        ))
        cached = res.scalar_one_or_none()
        if cached: return {"explanation": cached.explanation}

    # Generate
    # Fetch text level
    text_level = "B1" # Default
    if req.text_id:
        res = await db.execute(select(Text.level).where(Text.id == req.text_id))
        text_level = res.scalar_one_or_none() or "B1"

    lang = current_user.interface_language
    target_lang_name = "Ukrainian" if lang == 'ukr' else "English"

    prompt = f"""
    Act as a concise German tutor for a {target_lang_name}-speaking student.
    Analyze this German sentence (Level {text_level}): "{req.sentence}"

    RULES FOR EXPLANATION:
    1. KEEP IT SHORT. Maximum 3-4 bullet points. No long paragraphs. No intro, no Let's start no small talk.
    2. DO NOT define obvious words (e.g., don't say "Computer is a noun").
    3. FOCUS ONLY on grammar nuances relevant to Level {text_level}:
       - Why this specific article/ending? (Case/Gender)
       - Word order (Why is the verb here?)
       - Verb conjugations or tenses.
    4. If the sentence is very simple (A1/A2), just give 1 sentence summary like: "Standard structure: Subject + Verb + Adjective."
    5. Highlight key grammar parts in **bold**.

    Respond in {target_lang_name}.
    """

    explanation = await services.explain_grammar_text(prompt, db=db)
    
    # Save
    if explanation and req.text_id:
        db.add(GrammarExplanation(
            text_id=req.text_id, 
            sentence_index=req.sentence_index,
            language=current_user.interface_language,
            explanation=explanation
        ))
        await billing.deduct_credits(current_user.id, billing.PRICING['grammar_explanation'])
        await db.commit()
        
    return {"explanation": explanation}

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
    
    # Fetch grammar availability
    g_res = await db.execute(select(GrammarExplanation.sentence_index).where(
        GrammarExplanation.text_id == text_id,
        GrammarExplanation.language == current_user.interface_language
    ))
    grammar_indices = g_res.scalars().all()

    # Fetch last quiz result
    q_res = await db.execute(select(QuizResult).where(
        QuizResult.user_id == current_user.id,
        QuizResult.text_id == text_id
    ).order_by(QuizResult.created_at.desc()).limit(1))
    last_result = q_res.scalar_one_or_none()
    
    last_result_data = None
    if last_result:
        last_result_data = {"score": last_result.score, "total_questions": last_result.total_questions}
    
    return {"text": text_model, "vocab": vocab_models, "last_quiz_result": last_result_data, "grammar_indices": grammar_indices}

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