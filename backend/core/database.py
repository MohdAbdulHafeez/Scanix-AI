# ==========================================================
# SCANIX AI
# CORE - DATABASE
# PostgreSQL connection and session management
# Production grade with connection pooling, health checks, and singleton manager
# ==========================================================


import asyncio
from typing import Any
from typing import AsyncGenerator
from typing import Dict
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from core.config import settings
from core.logging import get_logger


logger = get_logger(__name__)


# ==========================================================
# BASE MODEL
# ==========================================================


class Base(DeclarativeBase):
    
    pass


# ==========================================================
# DATABASE MANAGER (Singleton Pattern)
# ==========================================================


class DatabaseManager:
    
    def __init__(self):
        
        self._engine = None
        
        self._async_session_maker = None
        
        self._initialized = False
        
        self._init_lock = asyncio.Lock()
        
        self._statement_timeout_ms: int = getattr(settings, "DATABASE_STATEMENT_TIMEOUT_MS", 30000)
    
    
    @property
    def is_initialized(self) -> bool:
        
        return self._initialized and self._engine is not None
    
    
    async def _verify_connection(self) -> None:
        """Verify database connectivity with SELECT 1"""
        if not self._engine:
            raise RuntimeError("Engine not initialized")
        
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            logger.debug("Database connection verified")
    
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(OperationalError),
        reraise=True
    )
    async def initialize(self) -> None:
        
        async with self._init_lock:
            
            if self._initialized:
                
                return
            
            if not settings.DATABASE_URL:
                
                logger.warning("DATABASE_URL not configured. Database features disabled.")
                
                self._initialized = True
                
                return
            
            # Convert PostgresDsn to string safely
            db_url = str(settings.DATABASE_URL)
            
            # Enforce async driver for PostgreSQL
            if db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
                logger.info("Converting to asyncpg driver for better async performance")
                db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            
            try:
                
                enable_auto_create = getattr(settings, "ENABLE_AUTO_CREATE_TABLES", False)
                
                # Create engine with optimized JSON serializers for AI/Metadata payloads
                self._engine = create_async_engine(
                    db_url,
                    echo=settings.DATABASE_ECHO,
                    pool_size=settings.DATABASE_POOL_SIZE,
                    max_overflow=settings.DATABASE_MAX_OVERFLOW,
                    pool_pre_ping=settings.DATABASE_POOL_PRE_PING,
                    pool_recycle=3600,
                    pool_timeout=30,
                    connect_args={
                        "timeout": 10,
                        "command_timeout": self._statement_timeout_ms // 1000,
                        "server_settings": {
                            "statement_timeout": f"{self._statement_timeout_ms}ms",
                            "lock_timeout": "10000ms",
                        },
                    } if "+asyncpg" in db_url else {
                        "connect_timeout": 10,
                    },
                    json_serializer=lambda obj: __import__('json').dumps(obj, ensure_ascii=False),
                )
                
                # Verify connection works before marking initialized
                await self._verify_connection()
                
                self._async_session_maker = async_sessionmaker(
                    self._engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                    autoflush=False,
                )
                
                if enable_auto_create and settings.ENV != "production":
                    
                    async with self._engine.begin() as conn:
                        
                        await conn.run_sync(Base.metadata.create_all)
                    
                    logger.info("Database tables created (auto-create enabled)")
                
                self._initialized = True
                
                logger.info(
                    "Database initialized successfully",
                    extra={
                        "pool_size": settings.DATABASE_POOL_SIZE,
                        "max_overflow": settings.DATABASE_MAX_OVERFLOW,
                        "driver": self._engine.driver,
                        "statement_timeout_ms": self._statement_timeout_ms,
                    },
                )
            
            except OperationalError as e:
                
                logger.error(f"Database connection failed after retries: {e}")
                
                raise
            
            except SQLAlchemyError as e:
                
                logger.error(f"Database initialization failed: {e}")
                
                raise
            
            except Exception as e:
                
                logger.error(f"Unexpected database initialization error: {e}")
                
                raise
    
    
    async def close(self) -> None:
        
        if self._engine:
            
            await self._engine.dispose()
            
            self._engine = None
            
            self._async_session_maker = None
            
            self._initialized = False
            
            logger.info("Database connection closed")
    
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        
        if not self.is_initialized:
            
            await self.initialize()
        
        if not self._async_session_maker:
            
            raise RuntimeError("Database not initialized. Check DATABASE_URL configuration.")
        
        async with self._async_session_maker() as session:
            
            try:
                
                # Yield control to the router/service layer. 
                # explicit session.commit() MUST be called by the service layer for writes.
                yield session
            
            except SQLAlchemyError as e:
                
                await session.rollback()
                
                logger.error(f"Database session SQLAlchemy error: {e}")
                
                raise
            
            except Exception as e:
                
                await session.rollback()
                
                logger.exception(f"Unexpected error in database session: {e}")
                
                raise
            
            finally:
                
                await session.close()
    
    
    async def check_liveness(self) -> Dict[str, Any]:
        """
        Liveness probe - checks if the database manager is alive.
        Does NOT perform deep connectivity checks.
        """
        return {
            "status": "alive" if self._engine is not None else "dead",
            "initialized": self._initialized,
            "database": "postgresql",
        }
    
    
    async def check_readiness(self) -> Dict[str, Any]:
        """
        Readiness probe - checks if database is ready to accept requests.
        Performs actual connectivity test.
        """
        if not self._engine:
            
            return {
                "ready": False,
                "database": "postgresql",
                "error": "Database engine not initialized",
                "pool_size": 0,
                "initialized": self._initialized,
            }
        
        try:
            
            async with self._engine.connect() as conn:
                
                await conn.execute(text("SELECT 1"))
            
            pool = self._engine.pool
            
            # Condense verbose getattr logic via functional fallbacks
            pool_status = {
                "size": getattr(pool, "size", lambda: 0)(),
                "checked_in": getattr(pool, "checkedin", lambda: 0)(),
                "overflow": getattr(pool, "overflow", lambda: 0)(),
            }
            
            return {
                "ready": True,
                "database": "postgresql",
                "pool_size": settings.DATABASE_POOL_SIZE,
                "max_overflow": settings.DATABASE_MAX_OVERFLOW,
                "pool_status": pool_status,
                "initialized": self._initialized,
            }
        
        except SQLAlchemyError as e:
            
            logger.error(f"Database readiness check failed: {e}")
            
            return {
                "ready": False,
                "database": "postgresql",
                "error": str(e),
                "initialized": self._initialized,
            }
        
        except Exception as e:
            
            logger.error(f"Unexpected readiness check error: {e}")
            
            return {
                "ready": False,
                "database": "postgresql",
                "error": "Unexpected error during readiness check",
                "initialized": self._initialized,
            }
    
    
    async def check_health(self) -> Dict[str, Any]:
        """
        Legacy health check endpoint - maintains backward compatibility.
        Combines liveness and readiness for simple health checks.
        """
        if not self._engine:
            
            return {
                "healthy": False,
                "database": "postgresql",
                "error": "Database engine not initialized",
                "pool_size": 0,
                "initialized": self._initialized,
            }
        
        try:
            
            async with self._engine.connect() as conn:
                
                await conn.execute(text("SELECT 1"))
            
            pool = self._engine.pool
            
            pool_status = {
                "size": getattr(pool, "size", lambda: 0)(),
                "checked_in": getattr(pool, "checkedin", lambda: 0)(),
                "overflow": getattr(pool, "overflow", lambda: 0)(),
            }
            
            return {
                "healthy": True,
                "database": "postgresql",
                "pool_size": settings.DATABASE_POOL_SIZE,
                "max_overflow": settings.DATABASE_MAX_OVERFLOW,
                "pool_status": pool_status,
                "initialized": self._initialized,
            }
        
        except SQLAlchemyError as e:
            
            logger.error(f"Database health check failed: {e}")
            
            return {
                "healthy": False,
                "database": "postgresql",
                "error": str(e),
                "initialized": self._initialized,
            }
        
        except Exception as e:
            
            logger.error(f"Unexpected health check error: {e}")
            
            return {
                "healthy": False,
                "database": "postgresql",
                "error": "Unexpected error during health check",
                "initialized": self._initialized,
            }
    
    
    async def execute_raw(self, query: str, params: Optional[Dict] = None) -> Any:
        """
        INTERNAL USE ONLY - Execute raw SQL queries.
        
        WARNING: This method should NEVER be exposed through public API routes.
        Only use for migrations, admin scripts, and internal operations.
        """
        if not self.is_initialized:
            
            await self.initialize()
        
        if not self._async_session_maker:
            
            raise RuntimeError("Database not initialized")
        
        # Safety guard: Block dangerous operations in production unless explicitly allowed
        query_upper = query.strip().upper()
        dangerous_keywords = ["DROP", "TRUNCATE", "ALTER TABLE", "CREATE TABLE"]
        
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                logger.warning(f"Blocked dangerous raw query: {query[:100]}")
                raise ValueError(f"Raw query with '{keyword}' is blocked for security reasons")
        
        async with self._async_session_maker() as session:
            
            try:
                
                # Set statement timeout for this specific query
                if self._statement_timeout_ms:
                    await session.execute(text(f"SET LOCAL statement_timeout = '{self._statement_timeout_ms}ms'"))
                
                result = await session.execute(text(query), params or {})
                
                await session.commit()
                
                return result
            
            except SQLAlchemyError as e:
                
                await session.rollback()
                
                logger.error(f"Raw query execution failed: {e}")
                
                raise


# ==========================================================
# GLOBAL DATABASE MANAGER INSTANCE
# ==========================================================


_db_manager = DatabaseManager()


# ==========================================================
# PUBLIC API
# ==========================================================


async def init_db() -> None:
    
    await _db_manager.initialize()


async def close_db() -> None:
    
    await _db_manager.close()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    
    async for session in _db_manager.get_session():
        
        yield session


async def check_db_connection() -> bool:
    
    health = await _db_manager.check_health()
    
    return health.get("healthy", False)


async def get_db_health() -> Dict[str, Any]:
    
    return await _db_manager.check_health()


async def get_db_liveness() -> Dict[str, Any]:
    """Liveness probe endpoint - use for /health/live"""
    return await _db_manager.check_liveness()


async def get_db_readiness() -> Dict[str, Any]:
    """Readiness probe endpoint - use for /health/ready"""
    return await _db_manager.check_readiness()


# ==========================================================
# END OF FILE
# ==========================================================