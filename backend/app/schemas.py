import re
import uuid
from datetime import datetime
from fastapi import Form
from fastapi.exceptions import RequestValidationError
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    conint,
    field_validator,
    model_validator,
    ValidationError,
    StringConstraints,
)
from typing import Optional, Annotated, List
from uuid import UUID
from app.models import WallpaperStatusEnum

# ---------------------------
# Shared Password Validation Mixin
# ---------------------------
class PasswordMixin(BaseModel):
    """Mixin for password validation with confirmation."""
    password: Annotated[str, StringConstraints(min_length=8)] = Field(
        ..., description="Password must be at least 8 characters"
    )
    confirm_password: str

    @field_validator("password", mode="before")
    def validate_password(cls, value: str):
        if not re.search(r"[A-Za-z]", value):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain at least one number")
        return value

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


# ---------------------------
# Signup Schema
# ---------------------------
class SignupSchema(PasswordMixin):
    username: Annotated[str, StringConstraints(min_length=3, max_length=50)]
    email: EmailStr

    class Config:
        json_schema_extra = {
            "example": {
                "username": "faiz",
                "email": "faiz@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
            }
        }


# ---------------------------
# Signup Form Dependency
# ---------------------------
def SignupForm(
    username: str = Form(...),
    email: EmailStr = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
) -> SignupSchema:
    try:
        return SignupSchema(
            username=username,
            email=email,
            password=password,
            confirm_password=confirm_password,
        )
    except ValidationError as e:
        raise RequestValidationError(e.errors())


# ---------------------------
# Reset Password Schema
# ---------------------------
class ResetPasswordSchema(PasswordMixin):
    class Config:
        json_schema_extra = {
            "example": {
                "password": "NewStrongPass123",
                "confirm_password": "NewStrongPass123",
            }
        }


# ---------------------------
# Reset Code Schema
# ---------------------------
class ResetCodeSchema(PasswordMixin):
    email: EmailStr
    code: conint(ge=100000, le=999999)

    class Config:
        json_schema_extra = {
            "example": {
                "email": "faiz@example.com",
                "code": 654321,
                "password": "NewStrongPass123",
                "confirm_password": "NewStrongPass123",
            }
        }


def ResetCodeForm(
    email: EmailStr = Form(...),
    code: int = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
) -> ResetCodeSchema:
    try:
        return ResetCodeSchema(
            email=email,
            code=code,
            password=password,
            confirm_password=confirm_password,
        )
    except ValidationError as e:
        raise RequestValidationError(e.errors())


# ---------------------------
# Login Schema
# ---------------------------
class LoginSchema(BaseModel):
    email: EmailStr
    password: str

    class Config:
        json_schema_extra = {
            "example": {"email": "faiz@example.com", "password": "StrongPass123"}
        }


# ---------------------------
# Forgot Password Schema
# ---------------------------
class ForgotPasswordSchema(BaseModel):
    email: EmailStr

    class Config:
        json_schema_extra = {"example": {"email": "faiz@example.com"}}


# ---------------------------
# Code Verification Schema
# ---------------------------
class CodeVerifySchema(BaseModel):
    email: EmailStr
    code: conint(ge=100000, le=999999)

    class Config:
        json_schema_extra = {"example": {"email": "faiz@example.com", "code": 123456}}


class ResendCodeSchema(BaseModel):
    email: EmailStr


# ---------------------------
# Update Password Schema
# ---------------------------
class UpdatePasswordSchema(PasswordMixin):
    old_password: str

    class Config:
        json_schema_extra = {
            "example": {
                "old_password": "StrongPass123",
                "password": "NewStrongPass123",
                "confirm_password": "NewStrongPass123",
            }
        }


def UpdatePasswordForm(
    old_password: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
) -> UpdatePasswordSchema:
    try:
        return UpdatePasswordSchema(
            old_password=old_password,
            password=password,
            confirm_password=confirm_password,
        )
    except ValidationError as e:
        raise RequestValidationError(e.errors())


# ---------------------------
# Update Profile Schema
# ---------------------------
class UpdateProfileSchema(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[
        Annotated[str, StringConstraints(pattern=r"^\+?\d{7,15}$")]
    ] = None
    username: Optional[Annotated[str, StringConstraints(min_length=3, max_length=50)]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "first_name": "first_Name",
                "last_name": "last_name",
                "phone_number": "+925551234567",
                "username": "Name_updated"
            }
        }


# ---------------------------
# Message Response Schema
# ---------------------------
class MessageResponse(BaseModel):
    message: str


# ---------------------------
# User Profile Response Schema
# ---------------------------
class UserProfileResponse(BaseModel):
    id: str
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: EmailStr
    phone_number: Optional[str] = None
    is_verified: bool
    profile_image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------
# Google Auth Schema
# ---------------------------
class GoogleAuthSchema(BaseModel):
    id_token: str
    name: Optional[str] = None
    picture: Optional[str] = None


# ---------------------------
# Token Response Schema
# ---------------------------
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None


# ---------------------------
# Wallpaper Schemas
# ---------------------------

class WallpaperCreateSchema(BaseModel):
    prompt: str = Field(..., min_length=3, description="Text prompt describing the wallpaper to generate")
    size: str = Field(..., description="Image size option (e.g. '1:1', '2:3 Portrait', '2:3 Landscape')")
    style: str = Field(..., description="Art style option (e.g. 'Colorful', '3D Render', 'Nature')")

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "A panda in a leather suit",
                "size": "2:3 Portrait",
                "style": "3D Render"
            }
        }


class WallpaperResponseSchema(BaseModel):
    id: UUID
    prompt: str
    size: str
    style: str
    status: WallpaperStatusEnum
    image_url: Optional[str] = Field(
        None, description="Relative path to the generated image (e.g. static/wallpapers/filename.png)"
    )
    full_image_url: Optional[str] = Field(
        None, description="Absolute URL to the generated image, useful for mobile/Flutter clients"
    )
    created_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "id": "uuid-string-here",
                "prompt": "A panda in a leather suit",
                "size": "2:3 Portrait",
                "style": "3D Render",
                "status": "completed",
                "image_url": "static/wallpapers/panda.png",
                "full_image_url": "http://localhost:8000/static/wallpapers/panda.png",
                "created_at": "2025-11-27T11:45:00"
            }
        }


class WallpaperListSchema(BaseModel):
    wallpapers: List[WallpaperResponseSchema]


class WallpaperDeleteResponse(BaseModel):
    message: str = Field(..., description="Confirmation message after deletion")
    deleted_wallpaper: Optional[WallpaperResponseSchema] = Field(
        None, description="Details of the deleted wallpaper, if available"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Wallpaper deleted successfully",
                "deleted_wallpaper": {
                    "id": "uuid-string-here",
                    "prompt": "A panda in a leather suit",
                    "size": "2:3 Portrait",
                    "style": "3D Render",
                    "status": "completed",
                    "image_url": "static/wallpapers/panda.png",
                    "full_image_url": "http://localhost:8000/static/wallpapers/panda.png",
                    "created_at": "2025-11-27T11:45:00"
                }
            }
        }
