import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import User
from ..schemas import TTSRequest, TTSPairRequest, TTSBatchRequest
from ..dependencies import get_current_user
from ..utils_tts import get_cached_or_generate_tts
from .. import cost_calculation

router = APIRouter(prefix="/api", tags=["tts"])

@router.post("/tts")
async def tts_endpoint(
    req: TTSRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    url = await get_cached_or_generate_tts(req.text, req.lang, current_user.id, db, source=req.source)
    if not url: raise HTTPException(500, "TTS Failed")
    return {"url": url}

@router.post("/tts_pair")
async def tts_pair_endpoint(
    req: TTSPairRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    urls = []
    de_url = await get_cached_or_generate_tts(req.de_text, 'de', current_user.id, db, source=req.source)
    if de_url: urls.append(de_url)
    
    trans_lang = 'uk' if current_user.interface_language == 'ukr' else 'en'
    if req.trans_text:
        parts = [p.strip() for p in re.split(r'[,;]', req.trans_text) if p.strip()]
        for part in parts:
            u = await get_cached_or_generate_tts(part, trans_lang, current_user.id, db, source=req.source)
            if u: urls.append(u)
            
    return {"urls": urls}

@router.post("/generate_audio_batch")
async def generate_audio_batch_endpoint(
    req: TTSBatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate audio for multiple sentences sequentially.
    Returns list of URLs and total cost.
    
    Retry strategy: Up to 2 attempts per sentence if generation fails.
    """
    urls = []
    failed_indices = []
    total_cost = 0.0
    
    for idx, sentence_text in enumerate(req.sentences):
        if not sentence_text or not sentence_text.strip():
            urls.append(None)
            continue
        
        audio_url = None
        retry_count = 0
        max_retries = 2
        
        # Try to generate audio (with retry)
        while retry_count <= max_retries and not audio_url:
            try:
                audio_url = await get_cached_or_generate_tts(
                    sentence_text,
                    req.lang,
                    current_user.id,
                    db
                )
            except Exception as e:
                print(f"⚠️ Error generating audio for sentence {idx} (attempt {retry_count + 1}): {e}")
                retry_count += 1
                if retry_count > max_retries:
                    failed_indices.append(idx)
                    break
                # Small delay before retry
                import asyncio
                await asyncio.sleep(0.5)
        
        urls.append(audio_url)
        
        # Record cost only if successfully generated
        if audio_url:
            try:
                cost = await cost_calculation.record_tts_text_generation_cost(
                    user_id=current_user.id,
                    text=sentence_text,
                    lang=req.lang,
                    job_name="generate_text_audio",
                    db=db
                )
                total_cost += cost
            except Exception as e:
                print(f"⚠️ Error recording cost for sentence {idx}: {e}")
    
    return {
        "success": True,
        "urls": urls,
        "completed": len(urls) - len(failed_indices),
        "failed_count": len(failed_indices),
        "failed_indices": failed_indices,
        "total_cost": total_cost,
        "message": f"Generated audio for {len(urls) - len(failed_indices)}/{len(req.sentences)} sentences"
    }