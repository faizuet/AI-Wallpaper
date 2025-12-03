from jose import jwt, JWTError, ExpiredSignatureError
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from uuid import uuid4
from app.core.config import settings

# ---------------------------
# Config
# ---------------------------
SECRET = settings.JWT_SECRET
ALGORITHM = settings.JWT_ALGORITHM

# OAuth2 scheme to extract Bearer token from Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ---------------------------
# Helper: create & decode JWT
# ---------------------------
def _create_token(data: dict, expires_minutes: int) -> str:
    """Helper to create a JWT with expiry."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET, algorithm=ALGORITHM)


def _decode_token(token: str) -> dict:
    """Helper to decode and validate a JWT."""
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


# ---------------------------
# Email Verification Token (15 minutes)
# ---------------------------
def create_email_verification_token(data: dict) -> str:
    """Create a JWT for email verification (expires in 15m)."""
    return _create_token(data, expires_minutes=15)


def decode_email_verification_token(token: str) -> dict:
    """Decode and validate an email verification token."""
    return _decode_token(token)


# ---------------------------
# Reset Password Token (15 minutes)
# ---------------------------
def create_reset_password_token(data: dict) -> str:
    """Create a JWT for password reset (expires in 15m)."""
    return _create_token(data, expires_minutes=15)


def decode_reset_password_token(token: str) -> dict:
    """Decode and validate a reset password token."""
    return _decode_token(token)


# ---------------------------
# Access Token (short-lived)
# ---------------------------
def create_access_token(data: dict) -> str:
    """Create a JWT for login sessions (expires in ACCESS_TOKEN_EXPIRE_MINUTES)."""
    return _create_token(data, expires_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token."""
    return _decode_token(token)


# ---------------------------
# Refresh Token
# ---------------------------
def create_refresh_token() -> str:
    """Generate a new opaque refresh token string (UUID)."""
    return str(uuid4())


def get_refresh_expiry() -> datetime:
    """Return expiry timestamp for refresh token (REFRESH_TOKEN_EXPIRE_DAYS)."""
    return datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)


# ---------------------------
# Current User Dependency
# ---------------------------
def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    FastAPI dependency to extract and validate the current user from JWT access token.
    Returns a dict with the user's email (sub).
    """
    payload = _decode_token(token)
    email: str = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    return {"sub": email}

