from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    BackgroundTasks,
    File,
    UploadFile,
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
    UpdatePasswordSchema,
    ResendCodeSchema,
)
from app.models import User, AuthProviderEnum, RefreshToken
from app.core.database import get_db
from app.api.routes.utils import hash_utils, jwt_utils, email_utils
from app.api.routes.utils.auth_utils import (
    get_user_by_email,
    ensure_local_account,
    validate_verification_code,
    validate_reset_code,
)
from app.core.config import settings


router = APIRouter(prefix="/auth", tags=["Auth"])

PROFILE_PIC_DIR = "static/profile_pics"


# ---------------------------
# Register Endpoint
# ---------------------------
@router.post("/register", response_model=MessageResponse)
async def register_user(
    form_data: SignupSchema = Depends(SignupForm),
    profile_image: UploadFile = File(...),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    username = form_data.username.strip()
    email = form_data.email.lower().strip()

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "Email already registered")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(400, "Username already taken")

    # Save profile image
    ext = os.path.splitext(profile_image.filename or "")[1]
    filename = f"{uuid4()}{ext}"
    os.makedirs(PROFILE_PIC_DIR, exist_ok=True)
    save_path = os.path.join(PROFILE_PIC_DIR, filename)
    with open(save_path, "wb") as f:
        f.write(await profile_image.read())

    hashed_password = hash_utils.hash_password(form_data.password)

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

    return {"message": "User registered successfully. Please check your email for the 6-digit code."}


# ---------------------------
# Verify Email
# ---------------------------
@router.post("/verify", response_model=MessageResponse)
def verify_email(payload: CodeVerifySchema, db: Session = Depends(get_db)):
    user = get_user_by_email(db, payload.email)

    if user.is_verified:
        return {"message": "Email already verified"}

    validate_verification_code(user, payload.code)

    user.is_verified = True
    user.verification_code = None
    user.verification_expires_at = None
    db.commit()

    return {"message": "Email verified successfully"}


# ---------------------------
# Resend Verification Code
# ---------------------------
@router.post("/resend-code", response_model=MessageResponse)
def resend_verification_code(
    payload: ResendCodeSchema,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    user = get_user_by_email(db, payload.email)

    if user.is_verified:
        return {"message": "Email is already verified"}

    new_code = random.randint(100000, 999999)
    user.verification_code = new_code
    user.verification_expires_at = datetime.utcnow() + timedelta(minutes=15)
    db.commit()

    if background_tasks:
        background_tasks.add_task(
            email_utils.send_verification_code_email, user.email, new_code
        )

    return {"message": "A new verification code has been sent to your email"}


# ---------------------------
# Login Endpoint
# ---------------------------
@router.post("/login", response_model=TokenResponse)
def login_user(payload: LoginSchema, db: Session = Depends(get_db)):
    user = get_user_by_email(db, payload.email)

    if not user.hashed_password or not hash_utils.verify_password(
        payload.password, user.hashed_password
    ):
        raise HTTPException(400, "Invalid email or password")

    ensure_local_account(user)

    if not user.is_verified:
        raise HTTPException(403, "Email not verified")

    access_token = jwt_utils.create_access_token({"sub": user.email})

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
# Refresh Token
# ---------------------------
@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(refresh_token: str, db: Session = Depends(get_db)):
    rt = db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
    if not rt:
        raise HTTPException(401, "Invalid refresh token")

    if rt.expires_at < datetime.utcnow():
        raise HTTPException(401, "Expired refresh token")

    user = db.query(User).filter(User.id == rt.user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    new_access = jwt_utils.create_access_token({"sub": user.email})

    return TokenResponse(access_token=new_access, refresh_token=refresh_token)


# ---------------------------
# Forgot Password
# ---------------------------
@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    payload: ForgotPasswordSchema,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    user = get_user_by_email(db, payload.email)
    ensure_local_account(user)

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
# Reset Password (JSON)
# ---------------------------
@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetCodeSchema, db: Session = Depends(get_db)):
    user = get_user_by_email(db, payload.email)
    ensure_local_account(user)
    validate_reset_code(user, payload.code)

    user.hashed_password = hash_utils.hash_password(payload.password)
    user.reset_code = None
    user.reset_expires_at = None
    db.commit()

    return {"message": "Password reset successful. You can now log in."}


# ---------------------------
# Google Sign-In
# ---------------------------
@router.post("/google", response_model=TokenResponse)
def google_sign_in(payload: GoogleAuthSchema, db: Session = Depends(get_db)):
    try:
        idinfo = id_token.verify_oauth2_token(
            payload.id_token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )

        if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise HTTPException(400, "Invalid issuer")

        email = (idinfo.get("email") or "").lower().strip()
        if not email:
            raise HTTPException(400, "Google token missing email")

        user = db.query(User).filter(User.email == email).first()

        if user and user.provider != AuthProviderEnum.google:
            raise HTTPException(
                400,
                "This email is registered with password. Please use standard login.",
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

        access_token = jwt_utils.create_access_token({"sub": user.email})

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
        raise HTTPException(400, "Invalid Google token")


# ---------------------------
# Sign Out
# ---------------------------
@router.post("/Sign-out", response_model=MessageResponse)
def logout_user(refresh_token: str, db: Session = Depends(get_db)):
    rt = db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
    if rt:
        db.delete(rt)
        db.commit()

    return {"message": "Signed out successfully"}

