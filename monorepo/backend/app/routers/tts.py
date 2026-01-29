import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import User
from ..schemas import TTSRequest, TTSPairRequest
from ..dependencies import get_current_user
from ..utils_tts import get_cached_or_generate_tts

router = APIRouter(prefix="/api", tags=["tts"])

@router.post("/tts")
async def tts_endpoint(
    req: TTSRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    url = await get_cached_or_generate_tts(req.text, req.lang, current_user.id, db)
    if not url: raise HTTPException(500, "TTS Failed")
    return {"url": url}

@router.post("/tts_pair")
async def tts_pair_endpoint(
    req: TTSPairRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    urls = []
    de_url = await get_cached_or_generate_tts(req.de_text, 'de', current_user.id, db)
    if de_url: urls.append(de_url)
    
    trans_lang = 'uk' if current_user.interface_language == 'ukr' else 'en'
    if req.trans_text:
        parts = [p.strip() for p in re.split(r'[,;]', req.trans_text) if p.strip()]
        for part in parts:
            u = await get_cached_or_generate_tts(part, trans_lang, current_user.id, db)
            if u: urls.append(u)
            
    return {"urls": urls}