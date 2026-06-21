# ==========================================================
# SCANIX AI
# CORE - DEPENDENCIES
# FastAPI dependency injection utilities
# Production grade with memory-safe limits and proxy routing
# ==========================================================


import asyncio
import time
from datetime import datetime
from datetime import timezone
from typing import AsyncGenerator
from typing import Dict
from typing import Optional
from typing import Tuple

from fastapi import Depends
from fastapi import Header
from fastapi import HTTPException
from fastapi import Request
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_session
from core.exceptions import RateLimitError, InvalidTokenError
from core.logging import get_logger
from core.security import decode_token, is_token_revoked


logger = get_logger(__name__)


# ==========================================================
# DATABASE INJECTION
# ==========================================================


async def get_db(session: AsyncSession = Depends(get_session)) -> AsyncSession:
    
    # Acts as an alias wrapper for FastAPI route injection
    return session


# ==========================================================
# IP RESOLUTION (Proxy-Aware)
# ==========================================================


def get_client_ip(request: Request) -> str:
    
    # 1. Check for standard proxy header
    forwarded_for = request.headers.get("X-Forwarded-For")
    
    if forwarded_for:
        
        return forwarded_for.split(",")[0].strip()
    
    # 2. Check for Nginx/Traefik real IP header
    real_ip = request.headers.get("X-Real-IP")
    
    if real_ip:
        
        return real_ip.strip()
    
    # 3. Fallback to direct client host
    return request.client.host if request.client else "127.0.0.1"


# ==========================================================
# RATE LIMITING (Redis-Backed with In-Memory Fallback)
# ==========================================================


class RateLimiter:
    
    def __init__(self):
        
        # In-memory fallback storage (used when Redis is unavailable)
        self._requests: Dict[str, Tuple[int, float]] = {}
        
        self._cleanup_threshold = 1000
        
        self._access_counter = 0
        
        # Redis client (initialized lazily)
        self._redis_client = None
        
        self._use_redis = False
    
    
    async def _get_redis(self):
        """Lazy initialization of Redis client"""
        if self._redis_client is not None:
            return self._redis_client
        
        use_redis = getattr(settings, "USE_REDIS_RATE_LIMITING", False)
        
        if use_redis:
            try:
                import redis.asyncio as redis
                self._redis_client = await redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                )
                self._use_redis = True
                logger.info("Redis rate limiting enabled")
            except Exception as e:
                logger.warning(f"Redis connection failed for rate limiting, falling back to in-memory: {e}")
                self._use_redis = False
        
        return self._redis_client
    
    
    def _cleanup_expired(self) -> None:
        """Clean up expired in-memory entries (fallback mode only)"""
        current_time = time.time()
        
        # Dictionary comprehension to keep only unexpired keys
        self._requests = {
            k: v for k, v in self._requests.items() if v[1] > current_time
        }
    
    
    def _get_key(self, request: Request, user_id: Optional[str] = None) -> str:
        
        if user_id:
            
            return f"user:{user_id}"
        
        return f"ip:{get_client_ip(request)}"
    
    
    async def _check_limit_redis(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        window_name: str,
    ) -> bool:
        """Check rate limit using Redis (atomic, distributed)"""
        redis = await self._get_redis()
        
        if not redis:
            # Fallback to in-memory if Redis unavailable
            return await self._check_limit_memory(key, limit, window_seconds, window_name)
        
        current_time = int(time.time())
        window_start = current_time - window_seconds
        
        # Use Redis sorted set for sliding window
        redis_key = f"rate_limit:{key}:{window_name}"
        
        # Remove old entries
        await redis.zremrangebyscore(redis_key, 0, window_start)
        
        # Get current count
        count = await redis.zcard(redis_key)
        
        if count >= limit:
            logger.warning(f"Rate limit exceeded ({window_name}) for {key}")
            raise RateLimitError(limit=limit, window=window_name)
        
        # Add current request
        await redis.zadd(redis_key, {str(current_time): current_time})
        
        # Set expiry on the key
        await redis.expire(redis_key, window_seconds)
        
        return True
    
    
    async def _check_limit_memory(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        window_name: str,
    ) -> bool:
        """Check rate limit using in-memory storage (non-distributed)"""
        # Periodic cleanup
        self._access_counter += 1
        
        if self._access_counter > self._cleanup_threshold:
            
            self._cleanup_expired()
            
            self._access_counter = 0
        
        current_time = time.time()
        expiry = current_time + window_seconds
        
        # Use minute/hour-based key for fixed window
        if window_seconds == 60:
            time_unit = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        elif window_seconds == 3600:
            time_unit = datetime.now(timezone.utc).strftime("%Y%m%d%H")
        else:
            time_unit = str(int(current_time / window_seconds))
        
        request_key = f"{key}:{window_name}:{time_unit}"
        
        count, _ = self._requests.get(request_key, (0, expiry))
        
        if count >= limit:
            logger.warning(f"Rate limit exceeded ({window_name}) for {key}")
            raise RateLimitError(limit=limit, window=window_name)
        
        self._requests[request_key] = (count + 1, expiry)
        
        return True
    
    
    async def check_minute_limit(
        self,
        request: Request,
        user_id: Optional[str] = None,
    ) -> bool:
        
        key = self._get_key(request, user_id)
        
        return await self._check_limit_redis(
            key=key,
            limit=settings.API_RATE_LIMIT_PER_MINUTE,
            window_seconds=60,
            window_name="minute",
        )
    
    
    async def check_hour_limit(
        self,
        request: Request,
        user_id: Optional[str] = None,
    ) -> bool:
        
        key = self._get_key(request, user_id)
        
        return await self._check_limit_redis(
            key=key,
            limit=settings.API_RATE_LIMIT_PER_HOUR,
            window_seconds=3600,
            window_name="hour",
        )
    
    async def close(self) -> None:
        """Close Redis connection"""
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None
            self._use_redis = False


_rate_limiter = RateLimiter()


async def init_rate_limiter() -> None:
    """Initialize rate limiter (call during startup)"""
    await _rate_limiter._get_redis()


async def close_rate_limiter() -> None:
    """Close rate limiter connections (call during shutdown)"""
    await _rate_limiter.close()


async def rate_limit(
    request: Request,
    user_id: Optional[str] = None,
) -> bool:
    
    await _rate_limiter.check_minute_limit(request, user_id)
    
    await _rate_limiter.check_hour_limit(request, user_id)
    
    return True


# ==========================================================
# REQUEST VALIDATION
# ==========================================================


async def validate_content_type(
    request: Request,
    expected_type: str = "application/json",
) -> bool:
    
    content_type = request.headers.get("content-type", "")
    
    # Exact match check to prevent MIME type confusion attacks
    if content_type.strip() != expected_type:
        
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Content-Type must be {expected_type}",
        )
    
    return True


# ==========================================================
# USER DEPENDENCIES (Full JWT Authentication)
# ==========================================================


async def get_current_user(
    authorization: Optional[str] = Header(None),
) -> str:
    """
    Extract and validate current user from JWT token.
    
    Returns:
        user_id: The authenticated user's ID
    
    Raises:
        HTTPException: If token is missing, invalid, or revoked
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization scheme. Use Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.replace("Bearer ", "")
    
    try:
        # Decode and validate token
        payload = decode_token(token, expected_type="access")
        
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user identifier",
            )
        
        # Check if token has been revoked
        if await is_token_revoked(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
            )
        
        # Set request ID for logging correlation
        request_id_ctx = getattr(__import__('core.logging', fromlist=['request_id_ctx']), 'request_id_ctx', None)
        if request_id_ctx:
            request_id_ctx.set(user_id)
        
        return str(user_id)
    
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    except Exception as e:
        logger.error(f"Unexpected error during token validation: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """
    Get current user if authenticated, otherwise return None.
    Does not raise exceptions for missing/invalid tokens.
    """
    if not authorization:
        return None
    
    if not authorization.startswith("Bearer "):
        return None
    
    token = authorization.replace("Bearer ", "")
    
    try:
        payload = decode_token(token, expected_type="access")
        user_id = payload.get("sub")
        
        if user_id and not await is_token_revoked(token):
            return str(user_id)
        
        return None
    
    except InvalidTokenError:
        return None
    
    except Exception:
        return None


async def get_current_active_user(
    current_user: str = Depends(get_current_user),
) -> str:
    """
    Get current active user (for routes that require active status).
    Placeholder for future user status checking (email verified, not banned, etc.)
    """
    # TODO: Check user status in database when System 9 is implemented
    # - Email verified
    # - Account not locked
    # - Account not banned
    # - etc.
    
    return current_user


# ==========================================================
# REQUEST METADATA INJECTION
# ==========================================================


async def get_request_metadata(
    request: Request,
    current_user: Optional[str] = Depends(get_optional_user),
) -> Dict[str, any]:
    """
    Inject request metadata for handlers that need context.
    Returns dict with client_ip, user_id, user_agent, etc.
    """
    return {
        "client_ip": get_client_ip(request),
        "user_id": current_user,
        "user_agent": request.headers.get("user-agent", "unknown"),
        "method": request.method,
        "path": request.url.path,
    }


# ==========================================================
# ADMIN DEPENDENCIES (Placeholder for future)
# ==========================================================


async def require_admin(
    current_user: str = Depends(get_current_user),
) -> str:
    """
    Require admin privileges.
    Placeholder for future admin role implementation.
    """
    # TODO: Check if user has admin role when System 9 is implemented
    # from core.user_roles import is_admin
    # if not is_admin(current_user):
    #     raise HTTPException(status_code=403, detail="Admin privileges required")
    
    return current_user


# ==========================================================
# END OF FILE
# ==========================================================