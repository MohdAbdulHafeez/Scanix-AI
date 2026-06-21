# ==========================================================
# SCANIX AI
# MAIN GATEWAY
# Enterprise FastAPI application entrypoint
# Features: Async lifespan, Correlation IDs, Schema-enforced errors
# ==========================================================


import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict
from typing import Any

from fastapi import FastAPI
from fastapi import Request
from fastapi import status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Core Infrastructure
from core.config import settings
from core.database import close_db
from core.database import init_db
from core.database import check_db_connection
from core.exceptions import ScanixException
from core.logging import get_api_logger
from core.logging import request_id_ctx
from core.responses import ErrorDetail
from core.responses import ErrorResponse

# Routers
from modules.scan.router import router as scan_router

# Schemas
from modules.scan.schemas import HealthCheckResponse


logger = get_api_logger()


# ==========================================================
# APP LIFECYCLE MANAGEMENT
# ==========================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    
    # Startup Sequence
    request_id_ctx.set("SYSTEM_BOOT")
    
    logger.info(f"Booting {settings.PROJECT} v{settings.VERSION} in {settings.ENV} mode...")
    
    try:
        await init_db()
        logger.info("Database initialization successful")
    except Exception:
        logger.exception("Database initialization failed")
        raise
    
    logger.info("System startup complete. Ready to accept connections.")
    
    yield
    
    # Shutdown Sequence
    request_id_ctx.set("SYSTEM_SHUTDOWN")
    
    logger.info("Initiating graceful shutdown sequence...")
    
    await close_db()
    
    logger.info("Shutdown complete.")


# ==========================================================
# FASTAPI INSTANTIATION
# ==========================================================


app = FastAPI(
    title=settings.PROJECT,
    version=settings.VERSION,
    description="Backend AI Pipeline for Scan Intelligence and Data Fusion",
    lifespan=lifespan,
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
)


# ==========================================================
# MIDDLEWARE
# ==========================================================


# 1. CORS Security
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 2. Telemetry & Correlation ID Injection
@app.middleware("http")
async def telemetry_middleware(request: Request, call_next):
    
    # Generate unique trace ID for this specific HTTP request
    req_id = str(uuid.uuid4())
    
    request_id_ctx.set(req_id)
    
    req_logger = get_api_logger(req_id)
    
    start_time = time.time()
    
    try:
        
        # Pass request down the pipeline
        response = await call_next(request)
        
        # Calculate processing time
        process_time_ms = int((time.time() - start_time) * 1000)
        
        # Inject trace metrics into HTTP response headers
        response.headers["X-Request-ID"] = req_id
        
        response.headers["X-Process-Time-Ms"] = str(process_time_ms)
        
        # Log slow requests
        if process_time_ms > 3000:
            req_logger.warning(f"Slow request detected: {request.method} {request.url.path} took {process_time_ms}ms")
            
        return response
        
    except Exception:
        
        # Catch unexpected fatal errors that bypass normal exception handlers
        req_logger.exception(f"Unhandled fatal server error: {e}")
        
        raise
    
    finally:
        # Clear correlation ID to prevent context leakage
        request_id_ctx.set(None)


# ==========================================================
# GLOBAL EXCEPTION HANDLERS
# ==========================================================


@app.exception_handler(ScanixException)
async def scanix_exception_handler(request: Request, exc: ScanixException):
    
    # Maps our custom domain errors directly to standard HTTP responses
    error_model = ErrorResponse(
        success=False,
        error=exc.error_code,
        message=exc.message,
        code=exc.error_code,
        details=[ErrorDetail(field=str(k),message=str(v), code="DETAIL") for k, v in exc.details.items()] if exc.details else []
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_model.model_dump(exclude_none=True),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    
    # Hijack FastAPI's default 422 array and map it to our ErrorResponse schema
    details = []
    
    for err in exc.errors():
        
        field = ".".join(str(loc) for loc in err.get("loc", []))
        
        details.append(
            ErrorDetail(
                field=field,
                message=err.get("msg", "Validation error"),
                code=err.get("type", "invalid"),
            )
        )
        
    error_model = ErrorResponse(
        success=False,
        error="VALIDATION_ERROR",
        message="The provided data failed validation constraints.",
        code="VALIDATION_ERROR",
        details=details,
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_model.model_dump(exclude_none=True),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    
    error_model = ErrorResponse(
        success=False,
        error="INTERNAL_SERVER_ERROR",
        message="An unexpected system error occurred.",
        code="INTERNAL_ERROR",
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_model.model_dump(exclude_none=True),
    )


# ==========================================================
# SYSTEM ROUTES
# ==========================================================


@app.get(
    "/",
    tags=["System"],
    summary="Root Endpoint",
    response_model=Dict[str, str]
)
async def root():
    """Root endpoint for deployment health probes."""
    return {
        "project": settings.PROJECT,
        "version": settings.VERSION,
        "status": "online"
    }


@app.get(
    "/health",
    tags=["System"],
    summary="System Health Check",
    response_model=HealthCheckResponse
)
async def health_check():
    """Comprehensive health check endpoint with database connectivity."""
    
    db_healthy = await check_db_connection()
    
    services = {
        "database": db_healthy,
        "api": True,
    }
    
    return HealthCheckResponse(
        status="healthy" if db_healthy else "degraded",
        version=settings.VERSION,
        timestamp=datetime.now(timezone.utc),
        services=services,
    )


# ==========================================================
# MODULE ROUTER MOUNTING
# ==========================================================

# Mount System 1: Scan Intelligence
app.include_router(scan_router, prefix=settings.API_V1_PREFIX)


# ==========================================================
# END OF FILE
# ==========================================================