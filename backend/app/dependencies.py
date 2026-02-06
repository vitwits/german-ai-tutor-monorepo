from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt
from pydantic import ValidationError
from datetime import datetime

from .database import get_db
from .models import User, UserBilling, BillingPlan
from .schemas import TokenData
from .security import SECRET_KEY, ALGORITHM
from .billing_logic import billing_manager

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # print(f"DEBUG: Token received: {token}")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("uid")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id)
    except (JWTError, ValidationError) as e:
        print(f"DEBUG: Auth failed: {e}")
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    # Process daily billing reset if needed
    await process_billing_reset(user.id, db)
    
    return user


async def process_billing_reset(user_id: str, db: AsyncSession) -> None:
    """
    Process daily and monthly billing resets for user if needed
    Called on every authenticated request
    """
    try:
        # Get billing plan
        plan_result = await db.execute(select(BillingPlan))
        billing_plan = plan_result.scalar_one_or_none()
        
        if not billing_plan:
            return  # No billing plan configured
        
        # Get user billing
        billing_result = await db.execute(
            select(UserBilling).where(UserBilling.user_id == user_id)
        )
        user_billing = billing_result.scalar_one_or_none()
        
        if not user_billing:
            return  # No billing for this user
        
        # Process reset
        updates = await billing_manager.process_daily_reset(
            user_billing,
            billing_plan.monthly_credit,
            billing_plan.max_cap_days,
            datetime.utcnow()
        )
        
        # Apply updates if any
        if updates:
            for key, value in updates.items():
                setattr(user_billing, key, value)
            
            await db.commit()
    except Exception as e:
        # Log but don't fail - billing reset is not critical
        print(f"WARNING: Billing reset failed for user {user_id}: {e}")