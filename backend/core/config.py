# ==========================================================
# SCANIX AI
# CORE - CONFIGURATION
# Production grade with V2 lifecycle validation
# ==========================================================

from enum import Enum
from functools import lru_cache
from typing import List, Literal

from pydantic import Field, model_validator, field_validator, AnyHttpUrl, RedisDsn, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import HttpUrl


# ==========================================================
# ENUMS FOR STRICT TYPE SAFETY
# ==========================================================

class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AIProvider(str, Enum):
    GEMINI = "gemini"
    GROQ = "groq"
    OPENROUTER = "openrouter"


class VoiceGender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


class VoiceMode(str, Enum):
    NORMAL = "normal"
    SLOW = "slow"
    FAST = "fast"


class OCRProvider(str, Enum):
    EASYOCR = "easyocr"
    TESSERACT = "tesseract"
    GOOGLE_VISION = "google_vision"


class VectorDB(str, Enum):
    QDRANT = "qdrant"
    PINECONE = "pinecone"
    CHROMA = "chroma"


class OFFCountry(str, Enum):
    WORLD = "world"
    INDIA = "india"
    US = "us"
    UK = "uk"
    FRANCE = "france"
    GERMANY = "germany"
    SPAIN = "spain"
    ITALY = "italy"


class Settings(BaseSettings):
    # ==========================================================
    # CORE
    # ==========================================================
    PROJECT: str = "SCANIX AI"
    APP_NAME: str = "SCANIX AI"
    VERSION: str = "1.0.0"
    PROJECT_MODE: str = "nutrition"
    ENV: Environment = Field(default=Environment.DEVELOPMENT)
    DEBUG: bool = True
    LOG_LEVEL: LogLevel = Field(default=LogLevel.INFO)
    HOST: str = "0.0.0.0"
    PORT: int = Field(default=8000, ge=1024, le=65535)
    API_V1_PREFIX: str = "/api/v1"
    APP_TIMEZONE: str = "Asia/Kolkata"

    # ==========================================================
    # VERSIONING
    # ==========================================================
    SCAN_ENGINE_VERSION: str = "1.0"
    HEALTH_ENGINE_VERSION: str = "1.0"
    TRUST_ENGINE_VERSION: str = "1.0"

    # ==========================================================
    # SECURITY
    # ==========================================================
    SECRET_KEY: str = Field(default="", min_length=32)
    # Explicitly fallback to SECRET_KEY if JWT_SECRET isn't isolated
    JWT_SECRET: str = Field(default="", min_length=32)
    JWT_EXPIRE_MINUTES: int = Field(default=60, ge=1, le=43200)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30, ge=1, le=365)
    ALLOWED_HOSTS: str = "*"
    API_RATE_LIMIT_PER_MINUTE: int = Field(default=60, ge=1, le=300)
    API_RATE_LIMIT_PER_HOUR: int = Field(default=1000, ge=1, le=10000)
    ACCESS_TOKEN_TYPE: str = "bearer"
    PASSWORD_HASH_ALGORITHM: str = "bcrypt"

    # ==========================================================
    # DATABASE
    # ==========================================================
    DATABASE_URL: PostgresDsn | None = Field(default=None)
    DATABASE_POOL_SIZE: int = Field(default=20, ge=5, le=100)
    DATABASE_MAX_OVERFLOW: int = Field(default=40, ge=10, le=200)
    DATABASE_ECHO: bool = False
    DATABASE_POOL_PRE_PING: bool = True
    DATABASE_STATEMENT_TIMEOUT_MS: int = Field(default=30000, ge=1000, le=300000)
    ENABLE_AUTO_CREATE_TABLES: bool = False

    # ==========================================================
    # REDIS CACHE
    # ==========================================================
    REDIS_URL: RedisDsn = Field(default="redis://localhost:6379")
    CACHE_TTL: int = Field(default=3600, ge=60, le=86400)
    SCAN_CACHE_TTL: int = Field(default=86400, ge=3600, le=604800)
    USE_REDIS_REVOCATION: bool = False
    REVOCATION_TTL_SECONDS: int = Field(default=604800, ge=86400, le=2592000)
    USE_REDIS_RATE_LIMITING: bool = False

    # ==========================================================
    # AI PROVIDERS
    # ==========================================================
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    TAVILY_API_KEY: str = ""

    ENABLE_GEMINI: bool = True
    ENABLE_GROQ: bool = True
    ENABLE_OPENROUTER: bool = True

    AI_DEFAULT_PROVIDER: AIProvider = Field(default=AIProvider.GEMINI)
    AI_FALLBACK_PROVIDER: AIProvider = Field(default=AIProvider.GROQ)
    AI_PROVIDER_STRATEGY: Literal["fallback", "round_robin", "priority"] = "fallback"
    AI_PROVIDER_ORDER: str = "gemini,groq,openrouter"

    AI_TIMEOUT_SECONDS: int = Field(default=30, ge=5, le=120)
    AI_MAX_RETRIES: int = Field(default=3, ge=1, le=10)
    AI_REQUESTS_PER_MINUTE: int = Field(default=60, ge=1, le=300)
    AI_REQUESTS_PER_DAY: int = Field(default=5000, ge=100, le=100000)
    AI_MAX_INPUT_TOKENS: int = Field(default=32000, ge=1000, le=200000)
    AI_MAX_OUTPUT_TOKENS: int = Field(default=4096, ge=256, le=32768)
    AI_ENABLE_FALLBACK: bool = True
    AI_ENABLE_CACHING: bool = True
    AI_CACHE_TTL_SECONDS: int = Field(default=86400, ge=3600, le=604800)

    # ==========================================================
    # MODELS
    # ==========================================================
    DEFAULT_MODEL: str = "gemini-2.5-flash"
    AI_PRIMARY_MODEL: str = "gemini-2.5-flash"
    AI_DEEP_MODEL: str = "gemini-2.5-flash"
    AI_EXPLAINER_MODEL: str = "gemini-2.5-flash"
    AI_AGENT_MODEL: str = "gemini-2.5-flash"
    AI_MEAL_MODEL: str = "gemini-2.5-flash"

    # ==========================================================
    # SYSTEM 1 - SCAN INTELLIGENCE
    # ==========================================================
    OPENFOODFACTS_URL: AnyHttpUrl = Field(default="https://world.openfoodfacts.org")  # type: ignore
    OPENFOODFACTS_TIMEOUT: int = Field(default=10, ge=5, le=60)
    OPENFOODFACTS_CACHE_TTL: int = Field(default=86400, ge=3600, le=604800)
    OPENFOODFACTS_USER_AGENT: str = "Scanix-AI/1.0"
    OPENFOODFACTS_COUNTRY: OFFCountry = Field(default=OFFCountry.WORLD)
    ENABLE_OPENFOODFACTS: bool = True
    ENABLE_BARCODE_SCAN: bool = True
    ENABLE_CAMERA_SCAN: bool = True
    ENABLE_MANUAL_BARCODE_ENTRY: bool = True
    MAX_SCAN_IMAGES: int = Field(default=4, ge=1, le=10)
    MAX_UPLOAD_MB: int = Field(default=10, ge=1, le=100)
    SCAN_MAX_IMAGE_DIMENSION: int = Field(default=4096, ge=512, le=8192)

    # ==========================================================
    # OCR
    # ==========================================================
    OCR_PROVIDER: OCRProvider = Field(default=OCRProvider.EASYOCR)
    OCR_FALLBACK: OCRProvider = Field(default=OCRProvider.TESSERACT)
    OCR_MIN_CONFIDENCE: float = Field(default=0.70, ge=0.0, le=1.0)
    OCR_MAX_TEXT_LENGTH: int = Field(default=25000, ge=1000, le=100000)
    OCR_LANGUAGES: str = "en"
    TESSERACT_PATH: str = ""
    OCR_TIMEOUT_SECONDS: int = Field(default=30, ge=10, le=120)

    # ==========================================================
    # SYSTEM 2 - INGREDIENT INTELLIGENCE
    # ==========================================================
    ENABLE_INGREDIENT_ANALYSIS: bool = True

    # ==========================================================
    # SYSTEM 3 & 4 - USDA / METABOLIC / DIGITAL TWIN
    # ==========================================================
    USDA_API_KEY: str = ""
    ENABLE_HEALTH_SCORING: bool = True
    HEALTH_SCORE_VERSION: str = "1.0"

    # ==========================================================
    # SYSTEM 5 - CONSUMER INTELLIGENCE
    # ==========================================================
    ENABLE_COMPLIANCE_ENGINE: bool = True

    # ==========================================================
    # SYSTEM 6 - TRUST INTELLIGENCE
    # ==========================================================
    ENABLE_TRUST_WEB_SEARCH: bool = True

    # ==========================================================
    # SYSTEM 7 - SMART FOOD INTELLIGENCE
    # ==========================================================
    ENABLE_PRODUCT_COMPARISON: bool = True
    RECOMMENDATION_VERSION: str = "1.0"

    # ==========================================================
    # SYSTEM 8 - AI HEALTH ASSISTANT
    # ==========================================================
    ENABLE_FOOD_EXPLAINER: bool = True
    ENABLE_NUTRITION_AGENT: bool = True
    ENABLE_MEAL_PLANNER: bool = True
    ENABLE_AGENT_MEMORY: bool = True

    # ==========================================================
    # RESEARCH LAYER
    # ==========================================================
    PUBMED_EMAIL: str = ""
    CROSSREF_BASE_URL: AnyHttpUrl = Field(default="https://api.crossref.org")  # type: ignore
    CROSSREF_MAILTO: str = ""
    RAG_MAX_RESULTS: int = Field(default=10, ge=1, le=50)
    RAG_MAX_SOURCES: int = Field(default=8, ge=1, le=20)
    RAG_SEARCH_TIMEOUT: int = Field(default=15, ge=5, le=60)
    RAG_CACHE_TTL: int = Field(default=86400, ge=3600, le=604800)
    PUBMED_MAX_RESULTS: int = Field(default=10, ge=1, le=50)
    CROSSREF_MAX_RESULTS: int = Field(default=10, ge=1, le=50)

    # ==========================================================
    # VECTOR DATABASE
    # ==========================================================
    ENABLE_RAG: bool = True
    VECTOR_DB: VectorDB = Field(default=VectorDB.QDRANT)
    QDRANT_URL: AnyHttpUrl | None = Field(default=None)  # type: ignore
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "scanix_food"
    QDRANT_DISTANCE: Literal["cosine", "euclidean", "dot"] = "cosine"

    # ==========================================================
    # VOICE AI
    # ==========================================================
    ENABLE_VOICE_CHAT: bool = True
    VOICE_PROVIDER: Literal["edge", "google", "azure", "elevenlabs"] = "edge"
    VOICE_MODE: VoiceMode = Field(default=VoiceMode.NORMAL)
    VOICE_LANGUAGE: str = "en"
    VOICE_NAME: str = "en-US-JennyNeural"
    VOICE_SPEED: float = Field(default=1.0, ge=0.5, le=2.0)
    VOICE_GENDER: VoiceGender = Field(default=VoiceGender.FEMALE)
    VOICE_TIMEOUT: int = Field(default=30, ge=5, le=120)
    WHISPER_MODEL: Literal["tiny.en", "base.en", "small.en", "medium.en"] = "small.en"

    # ==========================================================
    # USER INTELLIGENCE
    # ==========================================================
    SCAN_HISTORY_LIMIT: int = Field(default=100, ge=10, le=1000)
    FAVORITES_LIMIT: int = Field(default=200, ge=10, le=2000)

    # ==========================================================
    # STORAGE
    # ==========================================================
    UPLOAD_DIR: str = "uploads"
    REPORTS_DIR: str = "reports"
    CACHE_DIR: str = "cache"
    MAX_FILE_SIZE_MB: int = Field(default=10, ge=1, le=100)
    ALLOWED_IMAGE_TYPES: str = "jpg,jpeg,png,webp"

    # ==========================================================
    # OBSERVABILITY
    # ==========================================================
    SENTRY_DSN: AnyHttpUrl | None = Field(default=None)  # type: ignore
    POSTHOG_API_KEY: str = ""
    LOG_SAMPLE_RATE: float = Field(default=1.0, ge=0.01, le=1.0)
    LOG_REDACT_PII: bool = True
    LOG_INCLUDE_TRACE_ID: bool = False
    LOG_INCLUDE_SPAN_ID: bool = False

    # ==========================================================
    # DEPLOYMENT
    # ==========================================================
    PROJECT_NAME: str = "scanix-ai"
    FRONTEND_URL: AnyHttpUrl = Field(default="http://localhost:3000")  # type: ignore
    BACKEND_URL: AnyHttpUrl = Field(default="http://localhost:8000")  # type: ignore
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # ==========================================================
    # BACKGROUND TASKS
    # ==========================================================
    CELERY_BROKER_URL: RedisDsn = Field(default="redis://localhost:6379")
    CELERY_RESULT_BACKEND: RedisDsn = Field(default="redis://localhost:6379")

    # ==========================================================
    # FUTURE INTEGRATIONS
    # ==========================================================
    SPOONACULAR_API_KEY: str = ""
    APININJAS_API_KEY: str = ""
    FATSECRET_CLIENT_ID: str = ""
    FATSECRET_CONSUMER_KEY: str = ""
    FATSECRET_CONSUMER_SECRET: str = ""
    OPENFDA_URL: AnyHttpUrl = Field(default="https://api.fda.gov")  # type: ignore
    OPENFDA_ENABLED: bool = True

    # ==========================================================
    # IMAGE QUALITY ENGINE (Production tuning)
    # ==========================================================
    BLUR_CALIBRATION_FACTOR: int = Field(default=500, ge=100, le=2000)
    EDGE_DENSITY_CALIBRATION_FACTOR: int = Field(default=200, ge=50, le=500)
    NOISE_VARIANCE_THRESHOLD: int = Field(default=25, ge=10, le=100)
    GLARE_THRESHOLD: int = Field(default=240, ge=200, le=255)
    GLARE_SCALE_FACTOR: int = Field(default=1000, ge=500, le=2000)
    MIN_EDGE_PIXELS: int = Field(default=500, ge=100, le=2000)

    # Quality weights (should sum to 1.0)
    QUALITY_WEIGHT_BLUR: float = Field(default=0.10, ge=0.05, le=0.30)
    QUALITY_WEIGHT_EDGE_DENSITY: float = Field(default=0.10, ge=0.05, le=0.30)
    QUALITY_WEIGHT_BRIGHTNESS: float = Field(default=0.05, ge=0.02, le=0.15)
    QUALITY_WEIGHT_CONTRAST: float = Field(default=0.05, ge=0.02, le=0.15)
    QUALITY_WEIGHT_GLARE: float = Field(default=0.05, ge=0.02, le=0.15)
    QUALITY_WEIGHT_LIGHTING: float = Field(default=0.10, ge=0.05, le=0.20)
    QUALITY_WEIGHT_RESOLUTION: float = Field(default=0.10, ge=0.05, le=0.20)
    QUALITY_WEIGHT_NOISE: float = Field(default=0.05, ge=0.02, le=0.15)
    QUALITY_WEIGHT_PERSPECTIVE: float = Field(default=0.10, ge=0.05, le=0.20)
    QUALITY_WEIGHT_COVERAGE: float = Field(default=0.20, ge=0.10, le=0.30)

    # ==========================================================
    # PARSED IMMUTABLE FIELDS (Populated during lifecycle initialization)
    # ==========================================================
    ALLOWED_HOSTS_LIST: List[str] = Field(default_factory=list)
    CORS_ORIGINS_LIST: List[AnyHttpUrl] = Field(default_factory=list)  # type: ignore
    ALLOWED_IMAGE_TYPES_LIST: List[str] = Field(default_factory=list)
    AI_PROVIDER_ORDER_LIST: List[AIProvider] = Field(default_factory=list)
    OCR_LANGUAGES_LIST: List[str] = Field(default_factory=list)

    # ==========================================================
    # FIELD VALIDATORS
    # ==========================================================
    @field_validator("AI_PROVIDER_ORDER")
    @classmethod
    def validate_ai_provider_order(cls, v: str) -> str:
        allowed = {"gemini", "groq", "openrouter"}
        providers = [p.strip() for p in v.split(",")]
        
        for provider in providers:
            if provider not in allowed:
                raise ValueError(
                    f"AI_PROVIDER_ORDER contains invalid provider '{provider}'. "
                    f"Allowed: {allowed}"
                )
        
        return v

    @field_validator("OCR_LANGUAGES")
    @classmethod
    def validate_ocr_languages(cls, v: str) -> str:
        allowed = {"en", "hi", "ta", "te", "kn", "ml", "mr", "bn", "gu", "pa", "or"}
        languages = [lang.strip() for lang in v.split(",")]
        
        for lang in languages:
            if lang not in allowed:
                raise ValueError(f"OCR language '{lang}' not supported. Allowed: {allowed}")
        
        return v

    @field_validator("ALLOWED_IMAGE_TYPES")
    @classmethod
    def validate_allowed_image_types(cls, v: str) -> str:
        allowed = {"jpg", "jpeg", "png", "webp", "gif", "bmp"}
        types = [t.strip().lower() for t in v.split(",")]
        
        for img_type in types:
            if img_type not in allowed:
                raise ValueError(f"Image type '{img_type}' not supported. Allowed: {allowed}")
        
        return v

    # ==========================================================
    # LIFECYCLE POST-INITIALIZATION & CROSS-FIELD VALIDATION
    # ==========================================================
    @model_validator(mode="after")
    def compute_and_validate_system(self) -> "Settings":
        # 1. Build optimized runtime lists
        self.ALLOWED_HOSTS_LIST = (
            ["*"] if self.ALLOWED_HOSTS == "*" 
            else [h.strip() for h in self.ALLOWED_HOSTS.split(",")]
        )
        
        # Parse CORS origins with validation
        cors_origins = []
        for origin in self.CORS_ORIGINS.split(","):
            origin = origin.strip()
            if origin == "*":
                cors_origins.append(origin)  # type: ignore
            else:
                try:
                    cors_origins.append(AnyHttpUrl(origin))  # type: ignore
                except Exception:
                    raise ValueError(f"Invalid CORS origin URL: {origin}")
        self.CORS_ORIGINS_LIST = cors_origins  # type: ignore
        
        self.ALLOWED_IMAGE_TYPES_LIST = [t.strip().lower() for t in self.ALLOWED_IMAGE_TYPES.split(",")]
        
        # Parse AI provider order with enum validation
        ai_providers = []
        for p in self.AI_PROVIDER_ORDER.split(","):
            p = p.strip()
            try:
                ai_providers.append(AIProvider(p))
            except ValueError:
                raise ValueError(f"Invalid AI provider in AI_PROVIDER_ORDER: '{p}'. Must be one of: gemini, groq, openrouter")
        self.AI_PROVIDER_ORDER_LIST = ai_providers
        
        self.OCR_LANGUAGES_LIST = [l.strip() for l in self.OCR_LANGUAGES.split(",")]
        
        # 2. Production Hardening Constraints
        if self.ENV == Environment.PRODUCTION:
            # Database validation
            if self.DATABASE_URL is None:
                raise ValueError("DATABASE_URL must be defined in production")
            
            # URL validations for production
            if str(self.FRONTEND_URL) in ["http://localhost:3000", "http://localhost:8000"]:
                raise ValueError("FRONTEND_URL must be changed from default localhost in production")
            
            if str(self.BACKEND_URL) in ["http://localhost:8000"]:
                raise ValueError("BACKEND_URL must be changed from default localhost in production")
            
            # Secret validations
            if not self.SECRET_KEY or len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY must be defined and at least 32 characters in production")
            
            if not self.JWT_SECRET or len(self.JWT_SECRET) < 32:
                raise ValueError("JWT_SECRET must be defined and at least 32 characters in production")
            
            # AI provider validation
            active_providers = []
            if self.GEMINI_API_KEY:
                active_providers.append("gemini")
            if self.GROQ_API_KEY:
                active_providers.append("groq")
            if self.OPENROUTER_API_KEY:
                active_providers.append("openrouter")
            
            if not active_providers:
                raise ValueError("Production requires at least one active AI provider key")
            
            # Redis validation
            if str(self.REDIS_URL) == "redis://localhost:6379":
                raise ValueError("REDIS_URL must be configured properly in production")
            
            # Disable debug in production
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production")
        
        # 3. Structural Alignment Checks
        provider_switches = {
            AIProvider.GEMINI: self.ENABLE_GEMINI,
            AIProvider.GROQ: self.ENABLE_GROQ,
            AIProvider.OPENROUTER: self.ENABLE_OPENROUTER,
        }
        
        if not provider_switches.get(self.AI_DEFAULT_PROVIDER, False):
            raise ValueError(
                f"Conflict detected: AI_DEFAULT_PROVIDER is set to '{self.AI_DEFAULT_PROVIDER.value}', "
                f"but ENABLE_{self.AI_DEFAULT_PROVIDER.value.upper()} is set to False."
            )
        
        # 4. Validate that fallback provider has API key if fallback strategy is enabled
        if self.AI_ENABLE_FALLBACK and self.AI_PROVIDER_STRATEGY == "fallback":
            fallback_active = False
            if self.AI_FALLBACK_PROVIDER == AIProvider.GEMINI and self.GEMINI_API_KEY:
                fallback_active = True
            elif self.AI_FALLBACK_PROVIDER == AIProvider.GROQ and self.GROQ_API_KEY:
                fallback_active = True
            elif self.AI_FALLBACK_PROVIDER == AIProvider.OPENROUTER and self.OPENROUTER_API_KEY:
                fallback_active = True
            
            if not fallback_active:
                raise ValueError(
                    f"AI fallback is enabled but fallback provider '{self.AI_FALLBACK_PROVIDER.value}' "
                    "does not have a valid API key configured"
                )
        
        # 5. Validate vector database configuration if RAG is enabled
        if self.ENABLE_RAG and self.VECTOR_DB == VectorDB.QDRANT:
            if self.QDRANT_URL is None:
                raise ValueError("QDRANT_URL must be configured when ENABLE_RAG is True and VECTOR_DB is qdrant")
        
        # 6. Validate voice configuration
        if self.ENABLE_VOICE_CHAT:
            if self.VOICE_SPEED < 0.5 or self.VOICE_SPEED > 2.0:
                raise ValueError("VOICE_SPEED must be between 0.5 and 2.0")
        
        # 7. Validate upload directory configuration
        if self.MAX_FILE_SIZE_MB <= 0:
            raise ValueError("MAX_FILE_SIZE_MB must be greater than 0")
        
        # 8. Validate rate limits make sense
        if self.API_RATE_LIMIT_PER_HOUR < self.API_RATE_LIMIT_PER_MINUTE:
            raise ValueError("API_RATE_LIMIT_PER_HOUR cannot be less than API_RATE_LIMIT_PER_MINUTE")
        
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        validate_default=True,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()