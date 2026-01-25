from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.security import OAuth2PasswordRequestForm
import uuid
import logging

from ..database import get_db
from ..models import User
from ..schemas import UserCreate, Token, UserRead, UserSettingsUpdate, UserLevelUpdate
from ..security import get_password_hash, verify_password, create_access_token
from ..dependencies import get_current_user

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
            level='A2',
            credits=1000.0
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        # Generate token
        access_token = create_access_token(data={"sub": new_user.email, "uid": new_user.id})
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
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
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserRead)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Returns the current authenticated user's data."""
    return current_user

@router.post("/settings")
async def update_settings(req: UserSettingsUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if req.interface_language: current_user.interface_language = req.interface_language
    if req.vocab_session_size: current_user.vocab_session_size = req.vocab_session_size
    await db.commit()
    return {"ok": True}

@router.post("/update_level")
async def update_level(req: UserLevelUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if req.level in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']:
        current_user.level = req.level
        await db.commit()
    return {"ok": True}