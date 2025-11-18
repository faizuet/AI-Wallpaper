from jose import jwt, JWTError, ExpiredSignatureError
from datetime import datetime, timedelta
import os

# ---------------------------
# Config
# ---------------------------
SECRET = os.getenv("JWT_SECRET", "supersecretkey123")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


# ---------------------------
# Email Verification Token (24 hours)
# ---------------------------
def create_email_verification_token(data: dict, expires_minutes: int = 60 * 24):
    """
    Create a token for email verification.
    Default expiry: 24 hours.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET, algorithm=ALGORITHM)


def decode_email_verification_token(token: str):
    """
    Decode and validate an email verification token.
    Raises ValueError if invalid or expired.
    """
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise ValueError("Verification token has expired")
    except JWTError:
        raise ValueError("Invalid verification token")


# ---------------------------
# Reset Password Token (15 minutes)
# ---------------------------
def create_reset_password_token(data: dict, expires_minutes: int = 15):
    """
    Create a short-lived token for password reset.
    Default expiry: 15 minutes.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET, algorithm=ALGORITHM)


def decode_reset_password_token(token: str):
    """
    Decode and validate a reset password token.
    Raises ValueError if invalid or expired.
    """
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise ValueError("Reset token has expired")
    except JWTError:
        raise ValueError("Invalid reset token")


# ---------------------------
# Access Token (for login sessions)
# ---------------------------
def create_access_token(data: dict, expires_minutes: int = 60 * 24 * 7):
    """
    Create a longer-lived access token for login sessions.
    Default expiry: 7 days.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET, algorithm=ALGORITHM)


def decode_access_token(token: str):
    """
    Decode and validate an access token.
    Raises ValueError if invalid or expired.
    """
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise ValueError("Access token has expired")
    except JWTError:
        raise ValueError("Invalid access token")

