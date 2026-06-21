# ==========================================================
# SCANIX AI
# CORE - EXCEPTIONS
# Custom exceptions with error codes, error IDs, and retry info
# Production grade with direct FastAPI HTTPException integration
# ==========================================================


import uuid
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from fastapi import HTTPException


class ScanixException(HTTPException):
    
    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        
        # Unique identifier for this specific error occurrence to track in logs
        self.error_id = str(uuid.uuid4())
        
        self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        # Format the detail payload for FastAPI's default exception handler
        detail_payload = self.to_dict()
        
        super().__init__(status_code=status_code, detail=detail_payload)
    
    
    def to_dict(self) -> Dict[str, Any]:
        
        return {
            "error_id": self.error_id,
            "timestamp": self.timestamp,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


# ==========================================================
# EXTERNAL SERVICE ERROR (Parent for external APIs)
# ==========================================================


class ExternalServiceError(ScanixException):
    
    def __init__(
        self,
        message: str,
        error_code: str = "EXTERNAL_SERVICE_ERROR",
        status_code: int = 502,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = True,
    ):
        
        details = details or {}
        details["retryable"] = retryable
        
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            details=details,
        )
        
        self.retryable = retryable


# ==========================================================
# SCAN PROCESSING ERRORS
# ==========================================================


class ScanProcessingError(ScanixException):
    
    def __init__(
        self,
        message: str = "Scan processing failed",
        details: Optional[Dict[str, Any]] = None,
    ):
        
        super().__init__(
            message=message,
            error_code="SCAN_PROCESSING_ERROR",
            status_code=500,
            details=details,
        )


# ==========================================================
# IMAGE QUALITY ERRORS
# ==========================================================


class ImageQualityError(ScanixException):
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        
        super().__init__(
            message=message,
            error_code="IMAGE_QUALITY_ERROR",
            status_code=422,
            details=details,
        )


class CorruptedImageError(ImageQualityError):
    
    def __init__(self, image_path: Optional[str] = None):
        
        details = {}
        if image_path:
            details["image_path"] = image_path
            
        super().__init__(
            message="Image file is corrupted or cannot be read",
            details=details,
        )


class UnsupportedImageFormatError(ImageQualityError):
    
    def __init__(self, format_type: str, supported_formats: List[str]):
        
        super().__init__(
            message=f"Unsupported image format: {format_type}",
            details={
                "format": format_type,
                "supported_formats": supported_formats,
            },
        )


# ==========================================================
# PRODUCT FUSION ERRORS
# ==========================================================


class ProductFusionError(ScanixException):
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        
        super().__init__(
            message=message,
            error_code="PRODUCT_FUSION_ERROR",
            status_code=422,
            details=details,
        )


class FusionNoMatchError(ProductFusionError):
    
    def __init__(self, sources_attempted: List[str]):
        
        super().__init__(
            message="No product identity could be established from available sources",
            details={"sources_attempted": sources_attempted},
        )


# ==========================================================
# VALIDATION ERRORS (App-level)
# ==========================================================


class ScanixValidationError(ScanixException):
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details=details,
        )


# ==========================================================
# FILE VALIDATION ERRORS
# ==========================================================


class FileValidationError(ScanixException):
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        
        super().__init__(
            message=message,
            error_code="FILE_VALIDATION_ERROR",
            status_code=400,
            details=details,
        )


class FileTooLargeError(FileValidationError):
    
    def __init__(self, max_size_mb: int, actual_size_mb: float):
        
        super().__init__(
            message=f"File size exceeds {max_size_mb}MB limit",
            details={
                "max_size_mb": max_size_mb,
                "actual_size_mb": round(actual_size_mb, 2),
            },
        )


class InvalidFileTypeError(FileValidationError):
    
    def __init__(self, allowed_types: List[str], received_type: str):
        
        super().__init__(
            message=f"Invalid file type. Allowed: {', '.join(allowed_types)}",
            details={
                "allowed_types": allowed_types,
                "received_type": received_type,
            },
        )


# ==========================================================
# OCR ERRORS
# ==========================================================


class OCRError(ScanixException):
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        
        super().__init__(
            message=message,
            error_code="OCR_ERROR",
            status_code=422,
            details=details,
        )


class OCRTimeoutError(OCRError):
    
    def __init__(self, timeout_seconds: float):
        
        super().__init__(
            message=f"OCR processing timed out after {timeout_seconds} seconds",
            details={"timeout_seconds": timeout_seconds},
        )


class OCRNoTextError(OCRError):
    
    def __init__(self):
        
        super().__init__(
            message="No readable text found in image",
            details={"suggestion": "Please ensure the label is clear and well-lit"},
        )


class OCRProviderError(OCRError):
    
    def __init__(self, provider: str, original_error: str):
        
        super().__init__(
            message=f"OCR provider '{provider}' failed: {original_error}",
            details={"provider": provider, "original_error": original_error},
        )


# ==========================================================
# BARCODE ERRORS
# ==========================================================


class BarcodeError(ScanixException):
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        
        super().__init__(
            message=message,
            error_code="BARCODE_ERROR",
            status_code=422,
            details=details,
        )


class BarcodeNotFoundError(BarcodeError):
    
    def __init__(self):
        
        super().__init__(
            message="No valid barcode found in image",
            details={"suggestion": "Try capturing the barcode clearly or search manually"},
        )


class InvalidBarcodeError(BarcodeError):
    
    def __init__(self, barcode: str):
        
        super().__init__(
            message=f"Invalid barcode format: {barcode}",
            details={"barcode": barcode, "suggestion": "Check if barcode is a valid EAN-8, EAN-13, or UPC"},
        )


class BarcodeServiceUnavailableError(BarcodeError):
    
    def __init__(self, service: str):
        
        super().__init__(
            message=f"Barcode service '{service}' is currently unavailable",
            details={"service": service, "retryable": True},
        )


# ==========================================================
# PRODUCT ERRORS
# ==========================================================


class ProductNotFoundError(ScanixException):
    
    def __init__(self, search_term: str):
        
        super().__init__(
            message=f"Product not found: {search_term}",
            error_code="PRODUCT_NOT_FOUND",
            status_code=404,
            details={"search_term": search_term},
        )


class ProductNotAvailableError(ScanixException):
    
    def __init__(self, product_name: str, reason: str = "Product data incomplete"):
        
        super().__init__(
            message=f"Product '{product_name}' is not available for analysis",
            error_code="PRODUCT_NOT_AVAILABLE",
            status_code=422,
            details={"product_name": product_name, "reason": reason},
        )


class OpenFoodFactsError(ExternalServiceError):
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        
        super().__init__(
            message=message,
            error_code="OPENFOODFACTS_ERROR",
            status_code=502,
            details=details,
            retryable=True,
        )


class OpenFoodFactsRateLimitError(OpenFoodFactsError):
    
    def __init__(self, retry_after_seconds: int = 60):
        
        super().__init__(
            message="OpenFoodFacts rate limit exceeded",
            details={"retry_after_seconds": retry_after_seconds},
        )


# ==========================================================
# RESOURCE CONFLICT ERRORS (409)
# ==========================================================


class ConflictError(ScanixException):
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        
        super().__init__(
            message=message,
            error_code="CONFLICT_ERROR",
            status_code=409,
            details=details,
        )


class UserAlreadyExistsError(ConflictError):
    
    def __init__(self, email: str):
        
        super().__init__(
            message=f"User with email '{email}' already exists",
            details={"email": email},
        )


class DuplicateFavoriteError(ConflictError):
    
    def __init__(self, product_id: str, user_id: str):
        
        super().__init__(
            message="Product already in favorites",
            details={"product_id": product_id, "user_id": user_id},
        )


class DuplicateScanError(ConflictError):
    
    def __init__(self, barcode: str):
        
        super().__init__(
            message=f"Product with barcode '{barcode}' already scanned recently",
            details={"barcode": barcode},
        )


# ==========================================================
# RESOURCE NOT FOUND ERRORS (404)
# ==========================================================


class ResourceNotFoundError(ScanixException):
    
    def __init__(self, resource_type: str, resource_id: str):
        
        super().__init__(
            message=f"{resource_type} not found: {resource_id}",
            error_code="RESOURCE_NOT_FOUND",
            status_code=404,
            details={"resource_type": resource_type, "resource_id": resource_id},
        )


class UserNotFoundError(ResourceNotFoundError):
    
    def __init__(self, user_id: str):
        
        super().__init__("User", user_id)


class MealPlanNotFoundError(ResourceNotFoundError):
    
    def __init__(self, plan_id: str):
        
        super().__init__("MealPlan", plan_id)


class HistoryNotFoundError(ResourceNotFoundError):
    
    def __init__(self, history_id: str):
        
        super().__init__("ScanHistory", history_id)


# ==========================================================
# AUTHENTICATION ERRORS
# ==========================================================


class AuthenticationError(ScanixException):
    
    def __init__(self, message: str = "Authentication failed"):
        
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401,
        )


class InvalidTokenError(AuthenticationError):
    
    def __init__(self, reason: Optional[str] = None):
        
        message = "Invalid or expired token"
        if reason:
            message = f"Invalid or expired token: {reason}"
        
        super().__init__(message=message)


class CredentialsError(AuthenticationError):
    
    def __init__(self):
        
        super().__init__(message="Invalid email or password")


class TokenExpiredError(AuthenticationError):
    
    def __init__(self):
        
        super().__init__(message="Token has expired")


class PermissionDeniedError(ScanixException):
    
    def __init__(self, message: str = "Permission denied"):
        
        super().__init__(
            message=message,
            error_code="PERMISSION_DENIED",
            status_code=403,
        )


# ==========================================================
# RATE LIMIT ERRORS
# ==========================================================


class RateLimitError(ExternalServiceError):
    
    def __init__(self, limit: int, window: str):
        
        super().__init__(
            message=f"Rate limit exceeded: {limit} requests per {window}",
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details={"limit": limit, "window": window},
            retryable=True,
        )


class DailyRequestLimitError(RateLimitError):
    
    def __init__(self, daily_limit: int):
        
        super().__init__(
            limit=daily_limit,
            window="day",
        )
        self.message = f"Daily request limit of {daily_limit} exceeded"
        self.error_code = "DAILY_RATE_LIMIT_EXCEEDED"


# ==========================================================
# AI PROVIDER ERRORS
# ==========================================================


class AIProviderError(ExternalServiceError):
    
    def __init__(self, provider: str, message: str):
        
        super().__init__(
            message=f"AI provider {provider} error: {message}",
            error_code="AI_PROVIDER_ERROR",
            status_code=502,
            details={"provider": provider},
            retryable=True,
        )


class AIProviderTimeoutError(AIProviderError):
    
    def __init__(self, provider: str, timeout_seconds: int):
        
        super().__init__(
            provider=provider,
            message=f"Request timed out after {timeout_seconds} seconds",
        )
        self.error_code = "AI_PROVIDER_TIMEOUT"


class AIProviderQuotaError(AIProviderError):
    
    def __init__(self, provider: str):
        
        super().__init__(
            provider=provider,
            message="API quota exceeded",
        )
        self.error_code = "AI_PROVIDER_QUOTA_EXCEEDED"
        self.retryable = False


class AllProvidersFailedError(ExternalServiceError):
    
    def __init__(self, providers: List[str]):
        
        super().__init__(
            message="All AI providers failed",
            error_code="ALL_AI_PROVIDERS_FAILED",
            status_code=503,
            details={"providers": providers, "attempted_count": len(providers)},
            retryable=False,
        )


class AIResponseValidationError(ScanixException):
    
    def __init__(self, provider: str, reason: str):
        
        super().__init__(
            message=f"Invalid response from AI provider '{provider}': {reason}",
            error_code="AI_RESPONSE_VALIDATION_ERROR",
            status_code=500,
            details={"provider": provider, "reason": reason},
        )


# ==========================================================
# DATABASE ERRORS
# ==========================================================


class DatabaseError(ScanixException):
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=500,
            details=details,
        )


class DatabaseConnectionError(DatabaseError):
    
    def __init__(self, original_error: str):
        
        super().__init__(
            message="Failed to connect to database",
            details={"original_error": original_error, "retryable": True},
        )


class DatabaseQueryError(DatabaseError):
    
    def __init__(self, query_type: str, original_error: str):
        
        super().__init__(
            message=f"Database query failed during {query_type}",
            details={"query_type": query_type, "original_error": original_error},
        )


# ==========================================================
# CACHE ERRORS
# ==========================================================


class CacheError(ScanixException):
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        
        super().__init__(
            message=message,
            error_code="CACHE_ERROR",
            status_code=500,
            details=details,
        )


class CacheConnectionError(CacheError):
    
    def __init__(self, redis_url: str):
        
        super().__init__(
            message="Failed to connect to Redis cache",
            details={"redis_url": redis_url, "retryable": True},
        )


# ==========================================================
# WEBHOOK / EXTERNAL INTEGRATION ERRORS
# ==========================================================


class WebhookError(ExternalServiceError):
    
    def __init__(self, webhook_url: str, message: str):
        
        super().__init__(
            message=f"Webhook delivery failed: {message}",
            error_code="WEBHOOK_ERROR",
            status_code=502,
            details={"webhook_url": webhook_url},
            retryable=True,
        )


# ==========================================================
# END OF FILE
# ==========================================================