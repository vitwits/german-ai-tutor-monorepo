from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv
import os

# Load .env from monorepo root
MONOREPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
load_dotenv(os.path.join(MONOREPO_ROOT, ".env"))

# Секретний ключ має бути в .env, тут фолбек для розробки
SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-this-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 година
REFRESH_TOKEN_EXPIRE_DAYS = 30  # 30 днів

# For new passwords, use bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

def verify_password(plain_password, hashed_password):
    """Verify password - supports both werkzeug.security (scrypt) and bcrypt formats"""
    if not hashed_password:
        return False
    
    # First try passlib (for bcrypt hashes)
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        pass
    
    # Fall back to werkzeug for scrypt hashes (old format)
    try:
        from werkzeug.security import check_password_hash
        return check_password_hash(hashed_password, plain_password)
    except Exception:
        return False

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Додаємо exp claim
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
