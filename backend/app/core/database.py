from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URI,
    echo=False
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for ORM models
Base = declarative_base()

def get_db():
    """FastAPI dependency that provides a database session and ensures closure after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

