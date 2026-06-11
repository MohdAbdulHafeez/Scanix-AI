from datetime import datetime
from datetime import timedelta
from datetime import timezone

from jose import JWTError
from jose import jwt

from passlib.context import CryptContext

from core.config import settings


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    """
    Hash plain text password.
    """

    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """
    Verify password against hash.
    """

    return pwd_context.verify(
        plain_password,
        hashed_password,
    )


def create_access_token(
    subject: str,
) -> str:
    """
    Generate JWT access token.
    """

    expires_at = datetime.now(
        timezone.utc
    ) + timedelta(
        minutes=settings.JWT_EXPIRE_MINUTES
    )

    payload = {
        "sub": subject,
        "type": "access",
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm="HS256",
    )


def create_refresh_token(
    subject: str,
) -> str:
    """
    Generate JWT refresh token.
    """

    expires_at = datetime.now(
        timezone.utc
    ) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    payload = {
        "sub": subject,
        "type": "refresh",
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm="HS256",
    )


def decode_token(
    token: str,
) -> dict:
    """
    Decode JWT token.
    """

    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
        )

    except JWTError:
        raise ValueError(
            "Invalid or expired token"
        )