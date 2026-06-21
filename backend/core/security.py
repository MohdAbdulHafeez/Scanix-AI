# ==========================================================
# SCANIX AI
# CORE - SECURITY
# JWT handling, password hashing, and security utilities
# Production grade with async offloading and strict type verification
# ==========================================================


import asyncio
import hashlib
import secrets
import re
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Set

import bcrypt
import jwt

from core.config import settings
from core.exceptions import InvalidTokenError


# ==========================================================
# CONSTANTS
# ==========================================================


JWT_ALGORITHM = "HS256"
JWT_ISSUER = "scanix-ai"
JWT_AUDIENCE = "scanix-api"

# Password strength constants
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


# ==========================================================
# PASSWORD STRENGTH VALIDATION
# ==========================================================


def validate_password_strength(password: str) -> None:
    """
    Validate password meets security requirements.
    
    Requirements:
    - Minimum 8 characters
    - Maximum 128 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character (@$!%*?&)
    
    Raises ValueError with specific message if validation fails.
    """
    if not password:
        raise ValueError("Password cannot be empty")
    
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long")
    
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password cannot exceed {MAX_PASSWORD_LENGTH} characters")
    
    if not re.search(r'[A-Z]', password):
        raise ValueError("Password must contain at least one uppercase letter")
    
    if not re.search(r'[a-z]', password):
        raise ValueError("Password must contain at least one lowercase letter")
    
    if not re.search(r'\d', password):
        raise ValueError("Password must contain at least one digit")
    
    if not re.search(r'[@$!%*?&]', password):
        raise ValueError("Password must contain at least one special character (@$!%*?&)")


# ==========================================================
# PASSWORD HASHING (Async non-blocking)
# ==========================================================


def _hash_password_sync(password: str) -> str:
    
    salt = bcrypt.gensalt()
    
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    
    return hashed.decode("utf-8")


def _verify_password_sync(plain_password: str, hashed_password: str) -> bool:
    
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


async def hash_password(password: str) -> str:
    
    # Offload CPU-bound hashing to a threadpool to prevent event loop blocking
    return await asyncio.to_thread(_hash_password_sync, password)


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    
    # Offload CPU-bound verification to a threadpool
    return await asyncio.to_thread(_verify_password_sync, plain_password, hashed_password)


# ==========================================================
# JWT TOKEN (Enhanced with JTI, ISS, AUD)
# ==========================================================


def _generate_jti() -> str:
    """Generate unique JWT ID for token tracking and revocation"""
    return secrets.token_urlsafe(16)


def create_access_token(
    user_id: str,
    expires_delta: Optional[timedelta] = None,
    jti: Optional[str] = None,
) -> str:
    
    if expires_delta:
        
        expire = datetime.now(timezone.utc) + expires_delta
    
    else:
        
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.JWT_EXPIRE_MINUTES
        )
    
    token_id = jti or _generate_jti()
    
    payload = {
        "sub": user_id,
        "jti": token_id,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    
    # Enforce explicit JWT_SECRET in production, fallback only in development
    if settings.ENV == "production":
        if not settings.JWT_SECRET:
            raise ValueError("JWT_SECRET must be defined in production")
        secret = settings.JWT_SECRET
    else:
        secret = settings.JWT_SECRET or settings.SECRET_KEY
    
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def create_refresh_token(
    user_id: str,
    jti: Optional[str] = None,
) -> str:
    
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    
    token_id = jti or _generate_jti()
    
    payload = {
        "sub": user_id,
        "jti": token_id,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
    }
    
    # Enforce explicit JWT_SECRET in production
    if settings.ENV == "production":
        if not settings.JWT_SECRET:
            raise ValueError("JWT_SECRET must be defined in production")
        secret = settings.JWT_SECRET
    else:
        secret = settings.JWT_SECRET or settings.SECRET_KEY
    
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_token(
    token: str,
    expected_type: str = "access",
    verify_jti: bool = False,
    revoked_jtis: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Decode and validate JWT token.
    
    Args:
        token: JWT token string
        expected_type: Expected token type ('access' or 'refresh')
        verify_jti: Whether to check if token is revoked
        revoked_jtis: Set of revoked JTI values (for token blacklist)
    
    Returns:
        Decoded token payload
    
    Raises:
        InvalidTokenError: If token is invalid, expired, or revoked
    """
    
    # Enforce explicit JWT_SECRET in production
    if settings.ENV == "production":
        if not settings.JWT_SECRET:
            raise InvalidTokenError("JWT_SECRET not configured")
        secret = settings.JWT_SECRET
    else:
        secret = settings.JWT_SECRET or settings.SECRET_KEY
    
    try:
        
        payload = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            options={
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": True,
            },
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
        )
        
        # Prevent token substitution attacks (using refresh token as access token)
        if payload.get("type") != expected_type:
            
            raise InvalidTokenError(f"Token type mismatch: expected {expected_type}")
        
        # Check for token revocation if enabled
        if verify_jti and revoked_jtis is not None:
            token_jti = payload.get("jti")
            if token_jti and token_jti in revoked_jtis:
                raise InvalidTokenError("Token has been revoked")
        
        return payload
    
    except jwt.ExpiredSignatureError:
        
        raise InvalidTokenError("Token has expired")
    
    except jwt.InvalidIssuerError:
        
        raise InvalidTokenError("Invalid token issuer")
    
    except jwt.InvalidAudienceError:
        
        raise InvalidTokenError("Invalid token audience")
    
    except jwt.InvalidTokenError as e:
        
        raise InvalidTokenError(f"Invalid token: {str(e)}")


def decode_token_with_context(
    token: str,
    expected_type: str = "access",
) -> Dict[str, Any]:
    """
    Decode token with full context (for backward compatibility).
    Does NOT check revocation by default.
    """
    return decode_token(token, expected_type, verify_jti=False, revoked_jtis=None)


def get_user_id_from_token(
    token: str,
    expected_type: str = "access",
) -> str:
    
    payload = decode_token(token, expected_type)
    
    user_id = payload.get("sub")
    
    if not user_id:
        
        raise InvalidTokenError("Token missing user identifier")
    
    return str(user_id)


def get_token_jti(token: str) -> str:
    """Extract JTI (JWT ID) from token for revocation tracking"""
    
    payload = decode_token(token, "access", verify_jti=False)
    
    jti = payload.get("jti")
    
    if not jti:
        raise InvalidTokenError("Token missing JTI claim")
    
    return str(jti)


def get_token_expiry(token: str) -> datetime:
    """Extract expiry timestamp from token"""
    
    payload = decode_token(token, "access", verify_jti=False)
    
    exp = payload.get("exp")
    
    if not exp:
        raise InvalidTokenError("Token missing expiry claim")
    
    return datetime.fromtimestamp(exp, tz=timezone.utc)


# ==========================================================
# TOKEN REVOCATION
# ==========================================================


class TokenRevocationManager:
    """
    Token revocation manager with Redis support.
    
    For production deployments, set USE_REDIS_REVOCATION=true and configure REDIS_URL.
    Falls back to in-memory storage for development/testing.
    """
    
    def __init__(self):
        self._revoked_tokens: Set[str] = set()
        self._user_tokens: Dict[str, Set[str]] = {}
        self._use_redis = False
        self._redis_client = None
    
    async def initialize(self) -> None:
        """Initialize Redis connection if configured"""
        use_redis = getattr(settings, "USE_REDIS_REVOCATION", False)
        
        if use_redis:
            try:
                import redis.asyncio as redis
                self._redis_client = await redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                )
                self._use_redis = True
            except Exception as e:
                # Fall back to in-memory with warning
                from core.logging import get_logger
                logger = get_logger("scanix.security")
                logger.warning(f"Redis connection failed, falling back to in-memory revocation: {e}")
                self._use_redis = False
    
    async def revoke_token(self, jti: str, user_id: Optional[str] = None) -> None:
        """Revoke a single token by its JTI"""
        if self._use_redis and self._redis_client:
            # Store with TTL (7 days default, longer than any token)
            ttl = getattr(settings, "REVOCATION_TTL_SECONDS", 604800)
            await self._redis_client.setex(f"revoked:{jti}", ttl, "1")
            
            if user_id:
                await self._redis_client.sadd(f"user_tokens:{user_id}", jti)
                await self._redis_client.expire(f"user_tokens:{user_id}", ttl)
        else:
            # In-memory fallback
            self._revoked_tokens.add(jti)
            
            if user_id:
                if user_id not in self._user_tokens:
                    self._user_tokens[user_id] = set()
                self._user_tokens[user_id].add(jti)
    
    async def revoke_all_user_tokens(self, user_id: str) -> None:
        """Revoke all tokens for a specific user (logout everywhere)"""
        if self._use_redis and self._redis_client:
            # Get all token JTIs for this user
            token_jtis = await self._redis_client.smembers(f"user_tokens:{user_id}")
            
            for jti in token_jtis:
                ttl = getattr(settings, "REVOCATION_TTL_SECONDS", 604800)
                await self._redis_client.setex(f"revoked:{jti}", ttl, "1")
            
            # Delete the user's token set
            await self._redis_client.delete(f"user_tokens:{user_id}")
        else:
            # In-memory fallback
            if user_id in self._user_tokens:
                for jti in self._user_tokens[user_id]:
                    self._revoked_tokens.add(jti)
                self._user_tokens[user_id].clear()
    
    async def is_revoked(self, jti: str) -> bool:
        """Check if a token has been revoked"""
        if self._use_redis and self._redis_client:
            return await self._redis_client.exists(f"revoked:{jti}") > 0
        else:
            return jti in self._revoked_tokens
    
    async def close(self) -> None:
        """Close Redis connection"""
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None
            self._use_redis = False


# Global revocation manager instance
_token_revocation_manager = TokenRevocationManager()


async def init_revocation_manager() -> None:
    """Initialize the revocation manager (call during startup)"""
    await _token_revocation_manager.initialize()


async def close_revocation_manager() -> None:
    """Close the revocation manager (call during shutdown)"""
    await _token_revocation_manager.close()


async def revoke_token(token: str, user_id: Optional[str] = None) -> None:
    """Revoke a token (add to blacklist)"""
    try:
        jti = get_token_jti(token)
        await _token_revocation_manager.revoke_token(jti, user_id)
    except InvalidTokenError:
        # Silently ignore invalid tokens during revocation
        pass


async def revoke_all_user_tokens(user_id: str) -> None:
    """Revoke all tokens for a user"""
    await _token_revocation_manager.revoke_all_user_tokens(user_id)


async def is_token_revoked(token: str) -> bool:
    """Check if a token has been revoked"""
    try:
        jti = get_token_jti(token)
        return await _token_revocation_manager.is_revoked(jti)
    except InvalidTokenError:
        return True  # Invalid tokens are considered revoked


# ==========================================================
# REFRESH TOKEN ROTATION
# ==========================================================


async def rotate_refresh_token(old_refresh_token: str, user_id: str) -> tuple[str, str]:
    """
    Rotate refresh token (invalidate old, create new).
    Returns (new_access_token, new_refresh_token)
    
    This implements refresh token rotation pattern for enhanced security.
    """
    # Revoke the old refresh token
    await revoke_token(old_refresh_token, user_id)
    
    # Create new tokens
    new_access_token = create_access_token(user_id)
    new_refresh_token = create_refresh_token(user_id)
    
    return new_access_token, new_refresh_token


# ==========================================================
# API KEY
# ==========================================================


def generate_api_key() -> str:
    
    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    
    # SHA-256 is safe here because token_urlsafe(32) provides ~256 bits of entropy
    # making it immune to rainbow table attacks without needing a salt
    return hashlib.sha256(api_key.encode()).hexdigest()


def validate_api_key_format(api_key: str) -> bool:
    """
    Validate that API key has correct format.
    
    API keys from secrets.token_urlsafe(32):
    - Length: 43 characters
    - Characters: A-Z, a-z, 0-9, -, _
    """
    if not api_key or len(api_key) != 43:
        return False
    
    # Valid characters: A-Z a-z 0-9 - _
    valid_chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
    
    return all(c in valid_chars for c in api_key)


# ==========================================================
# CORS
# ==========================================================


def get_cors_origins() -> List[str]:
    
    # Utilizing the pre-compiled immutable list from updated config
    # Convert AnyHttpUrl objects to strings for CORS middleware
    cors_origins = []
    
    for origin in settings.CORS_ORIGINS_LIST:
        if origin == "*":
            cors_origins.append("*")
        else:
            cors_origins.append(str(origin))
    
    return cors_origins


# ==========================================================
# ADDITIONAL SECURITY UTILITIES
# ==========================================================


def generate_secure_random_string(length: int = 32) -> str:
    """Generate a cryptographically secure random string"""
    return secrets.token_urlsafe(length)


def constant_time_compare(val1: str, val2: str) -> bool:
    """
    Constant-time string comparison to prevent timing attacks.
    Uses secrets.compare_digest for security.
    """
    return secrets.compare_digest(val1.encode(), val2.encode())


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    Mask sensitive data for logging (e.g., API keys, tokens).
    
    Example: "sk_live_abc123xyz" -> "sk_live_******xyz"
    """
    if not data or len(data) <= visible_chars * 2:
        return "***MASKED***"
    
    prefix = data[:visible_chars]
    suffix = data[-visible_chars:]
    masked = "*" * min(8, len(data) - visible_chars * 2)
    
    return f"{prefix}{masked}{suffix}"


# ==========================================================
# END OF FILE
# ==========================================================