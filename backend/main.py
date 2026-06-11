from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown lifecycle.
    """

    print(f"Starting {settings.APP_NAME} v{settings.VERSION}")

    yield

    print(f"Stopping {settings.APP_NAME}")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.CORS_ORIGINS.split(",")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/",
    tags=["System"],
)
async def root():
    return {
        "project": settings.PROJECT,
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENV,
        "status": "running",
    }


@app.get(
    "/health",
    tags=["System"],
)
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
    }