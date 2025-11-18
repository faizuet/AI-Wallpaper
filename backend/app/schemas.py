from pydantic import BaseModel, EmailStr, Field, constr, field_validator
import re

# ---------------------------
# Shared Password Validation Mixin
# ---------------------------
class PasswordMixin(BaseModel):
    password: constr(min_length=8) = Field(..., description="Password must be at least 8 characters, include letters and numbers")
    confirm_password: str

    @field_validator("password")
    def validate_password(cls, value):
        if not re.search(r"[A-Za-z]", value):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain at least one number")
        return value

    @field_validator("confirm_password")
    def passwords_match(cls, value, info):
        password = info.data.get("password")
        if password and value != password:
            raise ValueError("Passwords do not match")
        return value


# ---------------------------
# Signup Schema
# ---------------------------
class SignupSchema(PasswordMixin):
    username: constr(min_length=3, max_length=50) = Field(..., description="Unique username")
    email: EmailStr = Field(..., description="Valid email address")

    class Config:
        json_schema_extra = {
            "example": {
                "username": "faiz",
                "email": "faiz@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123"
            }
        }


# ---------------------------
# Reset Password Schema
# ---------------------------
class ResetPasswordSchema(PasswordMixin):
    class Config:
        json_schema_extra = {
            "example": {
                "password": "NewStrongPass123",
                "confirm_password": "NewStrongPass123"
            }
        }


# ---------------------------
# Login Schema
# ---------------------------
class LoginSchema(BaseModel):
    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., description="User password")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "faiz@example.com",
                "password": "StrongPass123"
            }
        }


# ---------------------------
# Forgot Password Schema
# ---------------------------
class ForgotPasswordSchema(BaseModel):
    email: EmailStr = Field(..., description="Registered email address")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "faiz@example.com"
            }
        }


# ---------------------------
# Message Response Schema
# ---------------------------
class MessageResponse(BaseModel):
    message: str = Field(..., description="Response message")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "User registered successfully. Please verify your email."
            }
        }

