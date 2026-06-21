# ==========================================================
# SCANIX AI
# CORE - INIT
# Centralized export registry for the core infrastructure layer
# ==========================================================


from core.config import settings

from core.database import (
    check_db_connection,
    close_db,
    get_session,
    init_db,
)

from core.dependencies import (
    get_client_ip,
    get_current_user,
    get_db,
    get_optional_user,
    rate_limit,
)

from core.exceptions import (
    AIProviderError,
    AllProvidersFailedError,
    AuthenticationError,
    BarcodeError,
    BarcodeNotFoundError,
    DatabaseError,
    FileTooLargeError,
    FileValidationError,
    InvalidBarcodeError,
    InvalidFileTypeError,
    InvalidTokenError,
    OCRError,
    OCRNoTextError,
    OCRTimeoutError,
    OpenFoodFactsError,
    PermissionDeniedError,
    ProductNotFoundError,
    RateLimitError,
    ScanixException,
)

from core.logging import (
    get_api_logger,
    get_logger,
    get_scan_logger,
    log,
    setup_logging,
)

from core.responses import (
    ErrorResponse,
    PaginatedResponse,
    SuccessResponse,
    error_response,
    paginated_response,
    success_response,
)

from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    get_cors_origins,
    get_user_id_from_token,
    hash_api_key,
    hash_password,
    verify_password,
)


# ==========================================================
# PUBLIC API REGISTRY
# ==========================================================


__all__ = [
    # Config
    "settings",
    
    # Database
    "check_db_connection",
    "close_db",
    "get_session",
    "init_db",
    
    # Dependencies
    "get_client_ip",
    "get_current_user",
    "get_db",
    "get_optional_user",
    "rate_limit",
    
    # Exceptions
    "AIProviderError",
    "AllProvidersFailedError",
    "AuthenticationError",
    "BarcodeError",
    "BarcodeNotFoundError",
    "DatabaseError",
    "FileTooLargeError",
    "FileValidationError",
    "InvalidBarcodeError",
    "InvalidFileTypeError",
    "InvalidTokenError",
    "OCRError",
    "OCRNoTextError",
    "OCRTimeoutError",
    "OpenFoodFactsError",
    "PermissionDeniedError",
    "ProductNotFoundError",
    "RateLimitError",
    "ScanixException",
    
    # Logging
    "get_api_logger",
    "get_logger",
    "get_scan_logger",
    "log",
    "setup_logging",
    
    # Responses
    "ErrorResponse",
    "PaginatedResponse",
    "SuccessResponse",
    "error_response",
    "paginated_response",
    "success_response",
    
    # Security
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "generate_api_key",
    "get_cors_origins",
    "get_user_id_from_token",
    "hash_api_key",
    "hash_password",
    "verify_password",
]


# ==========================================================
# END OF FILE
# ==========================================================