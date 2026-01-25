import json
import uuid
import math
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..database import get_db
from ..models import User, Text, Vocabulary, GrammarExplanation
from ..schemas import TextGenerateRequest, TextReadSchema, ToggleFavRequest, GrammarExplainRequest, QuizResultRequest, VocabWordSchema
from ..dependencies import get_current_user
from .. import services, billing

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
    
    # Generation
    data = services.generate_german_text(req.topic, count, req.level, req.style)
    
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

    total_count_res = await db.execute(count_query)
    total_count = total_count_res.scalar_one()

    query = query.order_by(Text.id.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    texts = result.scalars().all()
    
    # Convert SQLAlchemy objects to Pydantic models to avoid serialization errors
    text_models = [TextReadSchema.model_validate(t) for t in texts]

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
    
    await db.delete(text)
    # Cascading deletes for vocab etc. should be handled by DB schema or manually here
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
    prompt = f"Explain grammar for: {req.sentence}" # Simplified prompt for brevity
    explanation = services.explain_grammar_text(prompt)
    
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
    
    return {"text": text_model, "vocab": vocab_models}