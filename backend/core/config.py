from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Global application settings.
    Loaded once from .env and cached.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # =====================================================
    # CORE
    # =====================================================

    PROJECT: str
    APP_NAME: str
    VERSION: str

    PROJECT_MODE: str

    ENV: str
    DEBUG: bool

    LOG_LEVEL: str

    HOST: str
    PORT: int

    API_V1_PREFIX: str

    APP_TIMEZONE: str

    # =====================================================
    # SECURITY
    # =====================================================

    SECRET_KEY: str
    JWT_SECRET: str

    JWT_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int

    ACCESS_TOKEN_TYPE: str = "bearer"

    PASSWORD_HASH_ALGORITHM: str = "bcrypt"

    ALLOWED_HOSTS: str

    API_RATE_LIMIT_PER_MINUTE: int
    API_RATE_LIMIT_PER_HOUR: int

    # =====================================================
    # DATABASE
    # =====================================================

    DATABASE_URL: str

    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40

    DATABASE_ECHO: bool = False
    DATABASE_POOL_PRE_PING: bool = True

    # =====================================================
    # CACHE
    # =====================================================

    REDIS_URL: str
    CACHE_TTL: int

    # =====================================================
    # AI
    # =====================================================

    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    TAVILY_API_KEY: str = ""

    AI_DEFAULT_PROVIDER: str
    AI_FALLBACK_PROVIDER: str

    AI_PROVIDER_STRATEGY: str
    AI_PROVIDER_ORDER: str

    AI_TIMEOUT_SECONDS: int
    AI_MAX_RETRIES: int

    AI_REQUESTS_PER_MINUTE: int
    AI_REQUESTS_PER_DAY: int

    AI_MAX_INPUT_TOKENS: int
    AI_MAX_OUTPUT_TOKENS: int

    AI_PRIMARY_MODEL: str
    AI_DEEP_MODEL: str

    AI_EXPLAINER_MODEL: str
    AI_AGENT_MODEL: str
    AI_MEAL_MODEL: str

    AI_ENABLE_FALLBACK: bool
    AI_ENABLE_CACHING: bool

    # =====================================================
    # FOOD DATA
    # =====================================================

    OPENFOODFACTS_URL: str

    OPENFOODFACTS_TIMEOUT: int
    OPENFOODFACTS_CACHE_TTL: int

    OPENFOODFACTS_USER_AGENT: str

    USDA_API_KEY: str = ""

    # =====================================================
    # OCR
    # =====================================================

    OCR_PROVIDER: str
    OCR_FALLBACK: str

    TESSERACT_PATH: str = ""

    # =====================================================
    # RAG
    # =====================================================

    ENABLE_RAG: bool

    VECTOR_DB: str

    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""

    QDRANT_COLLECTION: str
    QDRANT_DISTANCE: str

    RAG_MAX_RESULTS: int
    RAG_MAX_SOURCES: int

    RAG_SEARCH_TIMEOUT: int
    RAG_CACHE_TTL: int

    # =====================================================
    # RESEARCH
    # =====================================================

    PUBMED_EMAIL: str = ""

    CROSSREF_BASE_URL: str
    CROSSREF_MAILTO: str = ""

    PUBMED_MAX_RESULTS: int
    CROSSREF_MAX_RESULTS: int

    # =====================================================
    # VOICE
    # =====================================================

    ENABLE_VOICE_CHAT: bool

    VOICE_PROVIDER: str
    VOICE_MODE: str

    VOICE_LANGUAGE: str
    VOICE_NAME: str

    VOICE_SPEED: float

    VOICE_GENDER: str

    VOICE_TIMEOUT: int

    WHISPER_MODEL: str

    # =====================================================
    # USER
    # =====================================================

    SCAN_HISTORY_LIMIT: int
    FAVORITES_LIMIT: int

    # =====================================================
    # STORAGE
    # =====================================================

    UPLOAD_DIR: str
    REPORTS_DIR: str
    CACHE_DIR: str

    MAX_FILE_SIZE_MB: int
    ALLOWED_IMAGE_TYPES: str

    # =====================================================
    # DEPLOYMENT
    # =====================================================

    FRONTEND_URL: str
    BACKEND_URL: str

    CORS_ORIGINS: str

    # =====================================================
    # OBSERVABILITY
    # =====================================================

    SENTRY_DSN: str = ""
    POSTHOG_API_KEY: str = ""

    # =====================================================
    # FEATURE FLAGS
    # =====================================================

    ENABLE_OPENFOODFACTS: bool
    ENABLE_BARCODE_SCAN: bool
    ENABLE_CAMERA_SCAN: bool

    ENABLE_INGREDIENT_ANALYSIS: bool

    ENABLE_HEALTH_SCORING: bool

    ENABLE_COMPLIANCE_ENGINE: bool

    ENABLE_TRUST_WEB_SEARCH: bool

    ENABLE_PRODUCT_COMPARISON: bool

    ENABLE_FOOD_EXPLAINER: bool
    ENABLE_NUTRITION_AGENT: bool
    ENABLE_MEAL_PLANNER: bool
    ENABLE_AGENT_MEMORY: bool


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()