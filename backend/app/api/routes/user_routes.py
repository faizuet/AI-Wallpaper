from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import os
from uuid import uuid4

from app.models import User
from app.core.database import get_db
from app.api.routes.utils import hash_utils, jwt_utils
from app.schemas import (
    MessageResponse,
    UpdatePasswordSchema,
    UserProfileResponse,
    UpdateProfileSchema,
)

router = APIRouter(prefix="/users", tags=["Users"])

PROFILE_PIC_DIR = "static/profile_pics"


# ---------------------------
# Get Current User Profile
# ---------------------------
@router.get("/me", response_model=UserProfileResponse, summary="Get current user profile")
def get_current_user(
    token: dict = Depends(jwt_utils.get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == token["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserProfileResponse(
        id=str(user.id),
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        phone_number=user.phone_number,
        is_verified=user.is_verified,
        profile_image_url=user.profile_image_url,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


# ---------------------------
# Update Personal Info
# ---------------------------
@router.patch("/me", response_model=MessageResponse, summary="Update personal information")
def update_profile(
    payload: UpdateProfileSchema,
    token: dict = Depends(jwt_utils.get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == token["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update fields only if provided
    if payload.first_name is not None:
        user.first_name = payload.first_name.strip()

    if payload.last_name is not None:
        user.last_name = payload.last_name.strip()

    if payload.phone_number is not None:
        user.phone_number = payload.phone_number.strip()

    if payload.username is not None:
        new_username = payload.username.strip()
        # Check if username is taken by someone else
        if db.query(User).filter(User.username == new_username, User.id != user.id).first():
            raise HTTPException(status_code=400, detail="Username already taken")
        user.username = new_username

    db.commit()
    db.refresh(user)

    return {"message": "Profile updated successfully"}


# ---------------------------
# Update Profile Picture
# ---------------------------
@router.put("/me/profile-pic", response_model=MessageResponse, summary="Update profile picture")
async def update_profile_picture(
    profile_image: UploadFile = File(...),
    token: dict = Depends(jwt_utils.get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == token["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Save new image
    ext = os.path.splitext(profile_image.filename or "")[1]
    filename = f"{uuid4()}{ext}"
    os.makedirs(PROFILE_PIC_DIR, exist_ok=True)
    save_path = os.path.join(PROFILE_PIC_DIR, filename)

    with open(save_path, "wb") as f:
        f.write(await profile_image.read())

    # Update DB
    user.profile_image_url = filename
    db.commit()
    db.refresh(user)

    return {"message": "Profile picture updated successfully"}


# ---------------------------
# Update Password
# ---------------------------
@router.put("/me/password", response_model=MessageResponse, summary="Update password")
def update_password(
    payload: UpdatePasswordSchema,
    token: dict = Depends(jwt_utils.get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == token["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate old password
    if not hash_utils.verify_password(payload.old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Old password is incorrect")

    # Update password
    user.hashed_password = hash_utils.hash_password(payload.password)
    db.commit()
    db.refresh(user)

    return {"message": "Password updated successfully"}

