from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    BackgroundTasks,
    File,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session
import random
import os
from uuid import uuid4
from datetime import datetime, timedelta

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from app.schemas import (
    SignupSchema,
    LoginSchema,
    ForgotPasswordSchema,
    MessageResponse,
    CodeVerifySchema,
    ResetCodeSchema,
    GoogleAuthSchema,
    TokenResponse,
    SignupForm,
    ResetCodeForm,
    UpdatePasswordForm,
    UpdatePasswordSchema,
    ResendCodeSchema,
)
from app.models import User, AuthProviderEnum, RefreshToken
from app.core.database import get_db
from app.api.routes.utils import hash_utils, jwt_utils, email_utils
from app.core.config import settings


router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)

PROFILE_PIC_DIR = "static/profile_pics"


# ---------------------------
# Register Endpoint
# ---------------------------
@router.post(
    "/register",
    response_model=MessageResponse,
    summary="Register a new user with profile picture",
)
async def register_user(
    form_data: SignupSchema = Depends(SignupForm),
    profile_image: UploadFile = File(...),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    username = form_data.username.strip()
    email = form_data.email.lower().strip()

    # Uniqueness checks
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    # Save profile image
    ext = os.path.splitext(profile_image.filename or "")[1]
    filename = f"{uuid4()}{ext}"
    os.makedirs(PROFILE_PIC_DIR, exist_ok=True)
    save_path = os.path.join(PROFILE_PIC_DIR, filename)
    with open(save_path, "wb") as f:
        f.write(await profile_image.read())

    hashed_password = hash_utils.hash_password(form_data.password)

    # Verification code
    code = random.randint(100000, 999999)

    new_user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        is_verified=False,
        provider=AuthProviderEnum.local,
        verification_code=code,
        verification_expires_at=datetime.utcnow() + timedelta(minutes=15),
        profile_image_url=filename,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    if background_tasks:
        background_tasks.add_task(
            email_utils.send_verification_code_email, new_user.email, code
        )

    return {
        "message": "User registered successfully. Please check your email for the 6-digit code."
    }


# ---------------------------
# Verify Email
# ---------------------------
@router.post("/verify", response_model=MessageResponse, summary="Verify user email with 6-digit code")
def verify_email(payload: CodeVerifySchema, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        return {"message": "Email already verified"}

    if (
        user.verification_code != payload.code
        or not user.verification_expires_at
        or datetime.utcnow() > user.verification_expires_at
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    user.is_verified = True
    user.verification_code = None
    user.verification_expires_at = None
    db.commit()

    return {"message": "Email verified successfully"}


# ---------------------------
# Resend Verification Code
# ---------------------------
@router.post(
    "/resend-code",
    response_model=MessageResponse,
    summary="Resend a new verification code to unverified users",
)
def resend_verification_code(
    payload: ResendCodeSchema,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        return {"message": "Email is already verified"}

    # Generate new code
    new_code = random.randint(100000, 999999)
    user.verification_code = new_code
    user.verification_expires_at = datetime.utcnow() + timedelta(minutes=15)
    db.commit()

    # Send email in background
    if background_tasks:
        background_tasks.add_task(
            email_utils.send_verification_code_email, user.email, new_code
        )

    return {"message": "A new verification code has been sent to your email"}


# ---------------------------
# Login Endpoint
# ---------------------------
@router.post("/login", response_model=TokenResponse, summary="Login user")
def login_user(payload: LoginSchema, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    if not user or not user.hashed_password or not hash_utils.verify_password(
        payload.password, user.hashed_password
    ):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    if user.provider != AuthProviderEnum.local:
        raise HTTPException(
            status_code=400,
            detail="This email uses Google Sign-In. Please sign in with Google.",
        )

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email not verified")

    # Create short-lived access token
    access_token = jwt_utils.create_access_token({"sub": user.email})

    # Create or replace refresh token (one per user) using helpers
    refresh_value = jwt_utils.create_refresh_token()
    expires_at = jwt_utils.get_refresh_expiry()

    existing = db.query(RefreshToken).filter(RefreshToken.user_id == user.id).first()
    if existing:
        existing.token = refresh_value
        existing.expires_at = expires_at
    else:
        db.add(RefreshToken(user_id=user.id, token=refresh_value, expires_at=expires_at))

    db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_value)


# ---------------------------
# Refresh Endpoint
# ---------------------------
@router.post("/refresh", response_model=TokenResponse, summary="Refresh access token")
def refresh_access_token(refresh_token: str, db: Session = Depends(get_db)):
    # Look up refresh token in DB
    rt = db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
    if not rt:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Check expiry using helper
    if rt.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Expired refresh token")

    # Ensure user still exists
    user = db.query(User).filter(User.id == rt.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Issue new short-lived access token
    new_access = jwt_utils.create_access_token({"sub": user.email})

    # Return same refresh token (no rotation for simplicity)
    return TokenResponse(access_token=new_access, refresh_token=refresh_token)

# ---------------------------
# Forgot Password Endpoint
# ---------------------------
@router.post("/forgot-password", response_model=MessageResponse, summary="Request password reset")
def forgot_password(
    payload: ForgotPasswordSchema,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.provider != AuthProviderEnum.local:
        raise HTTPException(
            status_code=400,
            detail="This account uses Google Sign-In and does not have a password.",
        )

    reset_code = random.randint(100000, 999999)
    user.reset_code = reset_code
    user.reset_expires_at = datetime.utcnow() + timedelta(minutes=15)
    db.commit()

    if background_tasks:
        background_tasks.add_task(
            email_utils.send_password_reset_code_email, user.email, reset_code
        )

    return {"message": "Password reset code sent to your email"}


# ---------------------------
# Reset Password Endpoint
# ---------------------------
@router.post("/reset-password", response_model=MessageResponse, summary="Reset user password with 6-digit code")
def reset_password(form_data: ResetCodeSchema = Depends(ResetCodeForm), db: Session = Depends(get_db)):
    email = form_data.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.provider != AuthProviderEnum.local:
        raise HTTPException(
            status_code=400,
            detail="This account uses Google Sign-In and does not have a password.",
        )

    if (
        user.reset_code != form_data.code
        or not user.reset_expires_at
        or datetime.utcnow() > user.reset_expires_at
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")

    user.hashed_password = hash_utils.hash_password(form_data.password)
    user.reset_code = None
    user.reset_expires_at = None
    db.commit()

    return {"message": "Password reset successful. You can now log in."}


# ---------------------------
# Google Sign-In Endpoint
# ---------------------------
@router.post("/google", response_model=TokenResponse, summary="Sign in with Google")
def google_sign_in(payload: GoogleAuthSchema, db: Session = Depends(get_db)):
    try:
        idinfo = id_token.verify_oauth2_token(
            payload.id_token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )

        if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise HTTPException(status_code=400, detail="Invalid issuer")

        email = (idinfo.get("email") or "").lower().strip()
        if not email:
            raise HTTPException(status_code=400, detail="Google token missing email")

        user = db.query(User).filter(User.email == email).first()

        if user and user.provider != AuthProviderEnum.google:
            raise HTTPException(
                status_code=400,
                detail="This email is registered with password. Please use standard login.",
            )

        if not user:
            base_username = (payload.name or email.split("@")[0]).strip()
            candidate = base_username or "user"
            suffix = 1

            while db.query(User).filter(User.username == candidate).first():
                candidate = f"{base_username}_{suffix}"
                suffix += 1

            user = User(
                username=candidate,
                email=email,
                hashed_password=None,
                is_verified=True,
                provider=AuthProviderEnum.google,
                profile_image_url=payload.picture,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # Create access token
        access_token = jwt_utils.create_access_token({"sub": user.email})

        # Create or replace refresh token
        refresh_value = str(uuid4())
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        existing = db.query(RefreshToken).filter(RefreshToken.user_id == user.id).first()
        if existing:
            existing.token = refresh_value
            existing.expires_at = expires_at
        else:
            db.add(RefreshToken(user_id=user.id, token=refresh_value, expires_at=expires_at))

        db.commit()

        return TokenResponse(access_token=access_token, refresh_token=refresh_value)

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Google token")


# ---------------------------
# Sign Out Endpoint
# ---------------------------
@router.post("/Sign-out", response_model=MessageResponse, summary="Sign out user")
def logout_user(refresh_token: str, db: Session = Depends(get_db)):
    """
    Sign out the current user by deleting their refresh token.
    Access tokens will expire naturally after their short lifetime.
    """
    rt = db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
    if not rt:
        # Even if not found, respond success to avoid leaking session state
        return {"message": "Signed out successfully"}

    db.delete(rt)
    db.commit()
    return {"message": "Signed out successfully"}

