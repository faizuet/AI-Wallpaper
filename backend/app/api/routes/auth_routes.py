from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.schemas import (
    SignupSchema,
    LoginSchema,
    ForgotPasswordSchema,
    MessageResponse,
    ResetPasswordSchema
)
from app.models import User
from app.core.database import get_db
from app.api.routes.utils import hash_utils, jwt_utils, email_utils
import asyncio

router = APIRouter()

# Helper wrapper to run async email functions inside BackgroundTasks
def run_async_email(func, *args, **kwargs):
    asyncio.run(func(*args, **kwargs))


# ---------------------------
# Register Endpoint
# ---------------------------
@router.post("/register", response_model=MessageResponse, summary="Register a new user")
def register_user(
    payload: SignupSchema,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    hashed_password = hash_utils.hash_password(payload.password)

    new_user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hashed_password,
        is_verified=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Use 24h email verification token
    token = jwt_utils.create_email_verification_token({"sub": new_user.email})

    # Send verification email asynchronously
    background_tasks.add_task(run_async_email, email_utils.send_verification_email, new_user.email, token)

    return {"message": "User registered successfully. Please verify your email."}


# ---------------------------
# Verify Email Endpoint
# ---------------------------
@router.get("/verify/{token}", response_model=MessageResponse, summary="Verify user email")
def verify_email(token: str, db: Session = Depends(get_db)):
    payload = jwt_utils.decode_email_verification_token(token)
    email = payload.get("sub")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        return {"message": "Email already verified"}

    user.is_verified = True
    db.commit()
    return {"message": "Email verified successfully"}


# ---------------------------
# Login Endpoint
# ---------------------------
@router.post("/login", response_model=MessageResponse, summary="Login user")
def login_user(payload: LoginSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not hash_utils.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email not verified")

    access_token = jwt_utils.create_access_token({"sub": user.email})
    return {"message": f"Login successful. Token: {access_token}"}


# ---------------------------
# Forgot Password Endpoint
# ---------------------------
@router.post("/forgot-password", response_model=MessageResponse, summary="Request password reset")
def forgot_password(
    payload: ForgotPasswordSchema,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Use 15m reset password token
    reset_token = jwt_utils.create_reset_password_token({"sub": user.email})

    # Send password reset email asynchronously
    background_tasks.add_task(run_async_email, email_utils.send_password_reset_email, user.email, reset_token)

    return {"message": "Password reset link sent to your email"}


# ---------------------------
# Reset Password Endpoint
# ---------------------------
@router.post("/reset-password/{token}", response_model=MessageResponse, summary="Reset user password")
def reset_password(token: str, payload: ResetPasswordSchema, db: Session = Depends(get_db)):
    try:
        data = jwt_utils.decode_reset_password_token(token)
        email = data.get("sub")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_utils.hash_password(payload.password)
    db.commit()

    return {"message": "Password reset successful. You can now log in."}

