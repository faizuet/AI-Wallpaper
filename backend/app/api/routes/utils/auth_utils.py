from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models import User, AuthProviderEnum


# ---------------------------
# Common User Fetching Logic
# ---------------------------
def get_user_by_email(db: Session, email: str) -> User:
    email = email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def ensure_local_account(user: User):
    if user.provider != AuthProviderEnum.local:
        raise HTTPException(
            status_code=400,
            detail="This account uses Google Sign-In and does not have a password.",
        )


# ---------------------------
# Verification Code Validation
# ---------------------------
def validate_verification_code(user: User, code: int):
    if (
        user.verification_code != code
        or not user.verification_expires_at
        or datetime.utcnow() > user.verification_expires_at
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")


# ---------------------------
# Reset Code Validation
# ---------------------------
def validate_reset_code(user: User, code: int):
    if (
        user.reset_code != code
        or not user.reset_expires_at
        or datetime.utcnow() > user.reset_expires_at
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")

