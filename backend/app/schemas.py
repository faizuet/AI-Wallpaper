import re
from datetime import datetime
from fastapi import Form, File, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    conint,
    field_validator,
    model_validator,
    StringConstraints,
)
from typing import Optional, Annotated, List
from uuid import UUID


# ---------------------------
# Shared Password Validation Mixin
# ---------------------------
class PasswordMixin(BaseModel):
    password: Annotated[str, StringConstraints(min_length=8)]
    confirm_password: str

    @field_validator("password", mode="before")
    def validate_password(cls, value: str):
        if not isinstance(value, str):
            raise ValueError("Password must be a string")

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
# Signup Schema (JSON + File)
# ---------------------------
class SignupSchema(PasswordMixin):
    username: Annotated[str, StringConstraints(min_length=3, max_length=50)]
    email: EmailStr


# Allowed image MIME types
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/jpg",
}


# ---------------------------
# Signup Form Dependency
# ---------------------------
def SignupForm(
    username: str = Form(...),
    email: EmailStr = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    profile_image: UploadFile = File(...)
) -> SignupSchema:

    # Validate username
    if len(username.strip()) < 3:
        raise RequestValidationError([
            {"loc": ["username"], "msg": "Username must be at least 3 characters long", "type": "value_error"}
        ])

    # Validate file type
    if profile_image.content_type not in ALLOWED_IMAGE_TYPES:
        raise RequestValidationError([
            {
                "loc": ["profile_image"],
                "msg": "Invalid file type. Only JPEG, PNG, JPG, and WEBP images are allowed.",
                "type": "value_error.file_type",
            }
        ])

    return SignupSchema(
        username=username,
        email=email,
        password=password,
        confirm_password=confirm_password,
    )


# ---------------------------
# Reset Password Schema (JSON)
# ---------------------------
class ResetPasswordSchema(PasswordMixin):
    pass


# ---------------------------
# Reset Code Schema (JSON)
# ---------------------------
class ResetCodeSchema(PasswordMixin):
    email: EmailStr
    code: conint(ge=100000, le=999999)


# ---------------------------
# Login Schema
# ---------------------------
class LoginSchema(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    def validate_password(cls, v):
        if not v.strip():
            raise ValueError("Password cannot be empty")
        return v


# ---------------------------
# Forgot Password Schema
# ---------------------------
class ForgotPasswordSchema(BaseModel):
    email: EmailStr


# ---------------------------
# Code Verification Schema
# ---------------------------
class CodeVerifySchema(BaseModel):
    email: EmailStr
    code: conint(ge=100000, le=999999)


# ---------------------------
# Resend Code Schema
# ---------------------------
class ResendCodeSchema(BaseModel):
    email: EmailStr


# ---------------------------
# Update Password Schema (JSON)
# ---------------------------
class UpdatePasswordSchema(PasswordMixin):
    old_password: str

    @field_validator("old_password")
    def validate_old_password(cls, v):
        if not v.strip():
            raise ValueError("Old password cannot be empty")
        return v


# ---------------------------
# Update Profile Schema
# ---------------------------
class UpdateProfileSchema(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[
        Annotated[str, StringConstraints(pattern=r"^\+?\d{7,15}$")]
    ] = None
    username: Optional[
        Annotated[str, StringConstraints(min_length=3, max_length=50)]
    ] = None

    @model_validator(mode="after")
    def validate_at_least_one_field(cls, values):
        if not any(values.values()):
            raise ValueError("At least one field must be provided for update")
        return values


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
    prompt: str = Field(..., min_length=3, max_length=255)
    size: str
    style: str

    @field_validator("prompt")
    def validate_prompt_length(cls, v):
        if len(v.strip()) < 3:
            raise ValueError("Prompt must be at least 3 characters long")
        if len(v) > 255:
            raise ValueError("Prompt is too long. Please keep it under 255 characters.")
        return v


class WallpaperResponseSchema(BaseModel):
    id: UUID
    prompt: str
    size: str
    style: str
    created_at: datetime


class WallpaperListSchema(BaseModel):
    wallpapers: List[WallpaperResponseSchema]


class WallpaperDeleteResponse(BaseModel):
    message: str
    deleted_wallpaper: Optional[WallpaperResponseSchema] = None


class AISuggestionSchema(BaseModel):
    prompt: str

    @field_validator("prompt")
    def validate_prompt(cls, v):
        if not v.strip():
            raise ValueError("Prompt cannot be empty")
        return v


class AISuggestionResponse(BaseModel):
    suggestion: str
