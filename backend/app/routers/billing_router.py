"""
Billing and Energy API endpoints
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import User
from ..dependencies import get_current_user
from ..services import get_user_energy_status

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/energy-status")
async def get_energy_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's energy status"""
    result = await get_user_energy_status(db, current_user.id)
    return result
