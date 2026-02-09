from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.security import OAuth2PasswordRequestForm
import uuid
import logging

from ..database import get_db
from ..models import User, UserBilling, BillingPlan
from ..schemas import UserCreate, Token, UserRead, UserSettingsUpdate, UserLevelUpdate, UserPasswordUpdate
from ..security import get_password_hash, verify_password, create_access_token, create_refresh_token
from ..dependencies import get_current_user
from ..billing_logic import billing_init

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=Token)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        # Check if user exists
        result = await db.execute(select(User).where(User.email == user_data.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create user
        new_user = User(
            id=str(uuid.uuid4()),
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            interface_language='ukr',
            level='A2'
        )
        db.add(new_user)
        await db.flush()  # Flush to ensure user exists before creating billing
        
        # Get default billing plan
        plan_result = await db.execute(select(BillingPlan))
        billing_plan = plan_result.scalar_one_or_none()
        
        if billing_plan:
            # Initialize user billing
            billing_data = billing_init.initialize_user_billing(
                user_id=new_user.id,
                monthly_credit_usd=billing_plan.monthly_credit,
                max_cap_days=billing_plan.max_cap_days
            )
            
            user_billing = UserBilling(
                user_id=billing_data['user_id'],
                subscription_status=billing_data['subscription_status'],
                billing_start_day=billing_data['billing_start_day'],
                billing_end_day=billing_data['billing_end_day'],
                energy_left=billing_data['energy_left'],
                daily_spending=billing_data['daily_spending'],
                price_per_point_usd=billing_data['price_per_point_usd'],
                last_energy_reset=billing_data['last_energy_reset'],
                last_billing_reset=billing_data['last_billing_reset']
            )
            db.add(user_billing)
        
        await db.commit()
        await db.refresh(new_user)
        
        # Generate tokens
        access_token = create_access_token(data={"sub": new_user.email, "uid": new_user.id})
        refresh_token = create_refresh_token(data={"sub": new_user.email, "uid": new_user.id})
        return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logging.error(f"REGISTRATION FAILED: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during registration.")

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    # OAuth2PasswordRequestForm expects 'username', we use 'email'
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    
    try:
        if not user or not verify_password(form_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception:
        # Catch passlib errors (like UnknownHashError) and treat as auth failure
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    access_token = create_access_token(data={"sub": user.email, "uid": user.id})
    refresh_token = create_refresh_token(data={"sub": user.email, "uid": user.id})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.get("/me", response_model=UserRead)
async def read_users_me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Returns the current authenticated user's data with billing info."""
    # Load billing data if available
    billing_result = await db.execute(
        select(UserBilling).where(UserBilling.user_id == current_user.id)
    )
    billing = billing_result.scalar_one_or_none()
    
    # Create response with billing data
    user_data = {
        "id": current_user.id,
        "email": current_user.email,
        "level": current_user.level,
        "interface_language": current_user.interface_language,
        "billing": {
            "energy_left": billing.energy_left if billing else 0.0,
            "daily_spending": billing.daily_spending if billing else 0.0,
            "price_per_point_usd": billing.price_per_point_usd if billing else 0.0,
            "subscription_status": billing.subscription_status if billing else "inactive",
            "billing_start_day": billing.billing_start_day if billing else 1
        } if billing else None
    }
    
    return user_data

@router.post("/settings")
async def update_settings(req: UserSettingsUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if req.interface_language: current_user.interface_language = req.interface_language
    if req.vocab_session_size: current_user.vocab_session_size = req.vocab_session_size
    if req.study_batch_size: current_user.study_batch_size = req.study_batch_size
    await db.commit()
    return {"ok": True}

@router.post("/update_level")
async def update_level(req: UserLevelUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if req.level in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']:
        current_user.level = req.level
        await db.commit()
    return {"ok": True}

@router.post("/change_password")
async def change_password(req: UserPasswordUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not verify_password(req.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect current password")
    
    current_user.password_hash = get_password_hash(req.new_password)
    await db.commit()
    return {"ok": True}

@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token_req: dict, db: AsyncSession = Depends(get_db)):
    """Refresh access token using refresh token"""
    from ..security import SECRET_KEY, ALGORITHM
    from jose import JWTError, jwt
    
    refresh_token = refresh_token_req.get('refresh_token')
    if not refresh_token:
        raise HTTPException(status_code=400, detail="refresh_token required")
    
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if email is None or token_type != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # Get user
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Generate new access token
        new_access_token = create_access_token(data={"sub": user.email, "uid": user.id})
        return {"access_token": new_access_token, "token_type": "bearer"}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")