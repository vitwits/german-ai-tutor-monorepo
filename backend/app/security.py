import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv

# У Docker змінні середовища будуть передані напряму, для локальної розробки load_dotenv() знайде .env у корені
load_dotenv()

# Секретний ключ має бути в .env, тут фолбек для розробки
SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-this-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 година
REFRESH_TOKEN_EXPIRE_DAYS = 30  # 30 днів

# For new passwords, use pbkdf2_sha256 (bcrypt has issues with current version)
# Support multiple schemes for backward compatibility with existing hashes
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256", "argon2", "bcrypt"],
    deprecated="auto",
    pbkdf2_sha256__default_rounds=29000
)

def verify_password(plain_password, hashed_password):
    """Verify password - supports multiple hashing schemes (bcrypt, argon2, pbkdf2, scrypt)"""
    if not hashed_password:
        return False
    
    # Try passlib verification first (supports bcrypt, argon2, pbkdf2_sha256, etc)
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except ValueError as e:
        # This can happen with bcrypt version mismatches
        print(f"Password verification error: {e}")
        pass
    except Exception as e:
        print(f"Unexpected error during password verification: {e}")
        pass
    
    # Fall back to werkzeug for scrypt hashes (old format from werkzeug.security)
    try:
        from werkzeug.security import check_password_hash
        return check_password_hash(hashed_password, plain_password)
    except Exception:
        return False

def get_password_hash(password):
    """Hash password using bcrypt. Falls back to pbkdf2 if bcrypt fails."""
    try:
        return pwd_context.hash(password, scheme="bcrypt")
    except (ValueError, Exception) as e:
        # If bcrypt fails (e.g., password too long), fall back to pbkdf2_sha256
        print(f"Bcrypt hashing failed ({e}), falling back to pbkdf2_sha256")
        try:
            return pwd_context.hash(password, scheme="pbkdf2_sha256")
        except Exception as e2:
            print(f"pbkdf2_sha256 hashing also failed: {e2}")
            raise

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
