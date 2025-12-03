import uuid
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class WallpaperStatusEnum(PyEnum):
    """Status options for wallpaper generation tasks."""
    pending = "pending"
    completed = "completed"
    failed = "failed"


class AuthProviderEnum(PyEnum):
    """Authentication provider options for users."""
    local = "local"
    google = "google"


class User(Base):
    """User model representing registered accounts."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Basic account info
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)
    is_verified = Column(Boolean, default=False)

    provider = Column(
        Enum(AuthProviderEnum, name="authproviderenum"),
        default=AuthProviderEnum.local,
        nullable=False
    )

    # Personal info fields
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    phone_number = Column(String(20), nullable=True)

    # Email verification
    verification_code = Column(Integer, nullable=True)
    verification_expires_at = Column(DateTime, nullable=True)

    # Password reset
    reset_code = Column(Integer, nullable=True)
    reset_expires_at = Column(DateTime, nullable=True)

    # Profile image
    profile_image_url = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    wallpapers = relationship(
        "Wallpaper",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # One refresh token per user
    refresh_token = relationship(
        "RefreshToken",
        uselist=False,
        back_populates="user",
        cascade="all, delete-orphan"
    )


class Wallpaper(Base):
    """Wallpaper model representing generated images."""
    __tablename__ = "wallpapers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    # Prompt and customization
    prompt = Column(String(255), nullable=False)
    size = Column(String(20), nullable=True)
    style = Column(String(50), nullable=True)

    # Result
    image_url = Column(String(255), nullable=True)
    status = Column(
        Enum(WallpaperStatusEnum, name="wallpaperstatusenum"),
        default=WallpaperStatusEnum.pending,
        nullable=False
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship back to user
    user = relationship("User", back_populates="wallpapers")


class RefreshToken(Base):
    """Single refresh token per user for session renewal."""
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    token = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship back to user (one-to-one)
    user = relationship("User", back_populates="refresh_token")

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_refresh_user"),
    )

