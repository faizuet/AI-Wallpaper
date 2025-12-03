from passlib.context import CryptContext

# Configure bcrypt with explicit rounds for consistency
pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12, deprecated="auto")

def hash_password(password: str) -> str:
    """
    Hash a plain-text password using bcrypt.
    Returns the hashed password string.
    """
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str | None) -> bool:
    """
    Verify a plain-text password against a hashed password.
    Returns True if valid, False otherwise.
    """
    if not hashed:
        return False
    return pwd_context.verify(plain, hashed)

