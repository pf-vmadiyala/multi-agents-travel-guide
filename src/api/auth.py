import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
import uuid
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.db.models import User, Trip
import src.db.crud as crud
from src.utils.errors import AuthenticationError, AuthorizationError, NotFoundError

# Load security configuration
JWT_SECRET = os.getenv("JWT_SECRET", "some-secure-random-string-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# OAuth2 scheme config (points to our login route)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


# ===== 1. SECURE PASSWORD HASHING (NATIVE) =====

def get_password_hash(password: str) -> str:
    """Generate a PBKDF2 HMAC-SHA256 hash using a cryptographically secure random salt."""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256", 
        password.encode("utf-8"), 
        salt.encode("utf-8"), 
        100000
    ).hex()
    return f"{salt}${pwd_hash}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against the stored salt and hash using a constant-time comparison."""
    try:
        salt, pwd_hash = hashed_password.split("$")
        check_hash = hashlib.pbkdf2_hmac(
            "sha256", 
            plain_password.encode("utf-8"), 
            salt.encode("utf-8"), 
            100000
        ).hex()
        return secrets.compare_digest(check_hash, pwd_hash)
    except Exception:
        return False


# ===== 2. JWT TOKEN ACTIONS =====

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Issue a signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt


# ===== 3. FASTAPI DEPENDENCIES FOR SECURING ENDPOINTS =====

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Decodes the Bearer token, validates expiration, and extracts the authenticated User.
    Raises AuthenticationError (401) on failure.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id_str: str = payload.get("sub")
        if not user_id_str:
            raise AuthenticationError("Token is missing user subject.")
        
        user_uuid = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise AuthenticationError("Could not validate authorization token.")
    
    user = await crud.get_user_by_id(db, user_uuid)
    if not user:
        raise AuthenticationError("User associated with this token does not exist.")
        
    return user


async def require_trip_ownership(
    trip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Trip:
    """
    Secures individual Trip endpoints.
    Fetches the Trip, verifies it exists, and asserts that the current_user is the owner.
    Raises NotFoundError (404) or AuthorizationError (403).
    """
    trip = await crud.get_trip(db, trip_id)
    if not trip:
        raise NotFoundError(f"Trip with ID '{trip_id}' not found.")
        
    if trip.user_id != current_user.user_id:
        raise AuthorizationError("Access denied: You do not own this trip itinerary.")
        
    return trip
