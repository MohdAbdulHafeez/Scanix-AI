# ==========================================================
# SCANIX AI
# CORE - RESPONSES
# Standardized API response models
# Production grade with V2 lifecycle hooks and timezone-aware UTC
# ==========================================================


from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Dict
from typing import Generic
from typing import List
from typing import Optional
from typing import TypeVar

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from core.logging import get_current_request_id, get_current_scan_id


T = TypeVar("T")


# ==========================================================
# UTILITIES
# ==========================================================


def generate_utc_timestamp() -> datetime:
    """
    Generate current UTC timestamp as datetime object.
    
    Returns datetime (not string) for proper OpenAPI schema generation.
    FastAPI/Pydantic will serialize to ISO format automatically.
    """
    return datetime.now(timezone.utc)


# ==========================================================
# METADATA MODELS
# ==========================================================


class ResponseMetadata(BaseModel):
    
    model_config = ConfigDict(extra="forbid")
    
    request_id: Optional[str] = None
    
    scan_id: Optional[str] = None
    
    api_version: str = "1.0.0"
    
    processing_time_ms: Optional[float] = None


class PaginationMetadata(BaseModel):
    
    model_config = ConfigDict(extra="forbid")
    
    total: int
    
    page: int
    
    page_size: int
    
    pages: int
    
    has_next: bool
    
    has_previous: bool


# ==========================================================
# PYDANTIC MODELS (Used for OpenAPI Schema Generation)
# ==========================================================


class ErrorDetail(BaseModel):
    
    model_config = ConfigDict(extra="forbid")
    
    field: Optional[str] = None
    
    message: str
    
    code: str


class ErrorResponse(BaseModel):
    
    model_config = ConfigDict(extra="forbid")
    
    success: bool = False
    
    error: str
    
    message: str
    
    code: str = "ERROR"
    
    details: List[ErrorDetail] = Field(default_factory=list)
    
    metadata: ResponseMetadata = Field(default_factory=ResponseMetadata)
    
    timestamp: datetime = Field(default_factory=generate_utc_timestamp)


class SuccessResponse(BaseModel, Generic[T]):
    
    model_config = ConfigDict(extra="forbid")
    
    success: bool = True
    
    data: T
    
    message: Optional[str] = None
    
    metadata: ResponseMetadata = Field(default_factory=ResponseMetadata)
    
    timestamp: datetime = Field(default_factory=generate_utc_timestamp)


class PaginatedResponse(BaseModel, Generic[T]):
    
    model_config = ConfigDict(extra="forbid")
    
    success: bool = True
    
    data: List[T]
    
    pagination: PaginationMetadata
    
    metadata: ResponseMetadata = Field(default_factory=ResponseMetadata)
    
    timestamp: datetime = Field(default_factory=generate_utc_timestamp)


# ==========================================================
# HELPER FUNCTIONS (Schema-Validated Dictionaries)
# ==========================================================


def _get_request_metadata() -> Dict[str, Any]:
    """Extract request correlation IDs from async context"""
    return {
        "request_id": get_current_request_id(),
        "scan_id": get_current_scan_id(),
        "api_version": "1.0.0",
    }


def success_response(
    data: Any,
    message: Optional[str] = None,
    request_id: Optional[str] = None,
    scan_id: Optional[str] = None,
    processing_time_ms: Optional[float] = None,
) -> Dict[str, Any]:
    
    metadata_dict = _get_request_metadata()
    
    if request_id:
        metadata_dict["request_id"] = request_id
    
    if scan_id:
        metadata_dict["scan_id"] = scan_id
    
    if processing_time_ms is not None:
        metadata_dict["processing_time_ms"] = processing_time_ms
    
    metadata = ResponseMetadata(**metadata_dict)
    
    response_model = SuccessResponse(
        data=data,
        message=message,
        metadata=metadata,
    )
    
    return response_model.model_dump(exclude_none=True)


def error_response(
    error: str,
    message: str,
    code: str = "ERROR",
    details: Optional[List[Dict[str, Any]]] = None,
    request_id: Optional[str] = None,
    scan_id: Optional[str] = None,
) -> Dict[str, Any]:
    
    parsed_details = []
    
    if details:
        
        parsed_details = [ErrorDetail(**d) for d in details]
    
    metadata_dict = _get_request_metadata()
    
    if request_id:
        metadata_dict["request_id"] = request_id
    
    if scan_id:
        metadata_dict["scan_id"] = scan_id
    
    metadata = ResponseMetadata(**metadata_dict)
    
    response_model = ErrorResponse(
        error=error,
        message=message,
        code=code,
        details=parsed_details,
        metadata=metadata,
    )
    
    return response_model.model_dump(exclude_none=True)


def paginated_response(
    data: List[Any],
    total: int,
    page: int,
    page_size: int,
    request_id: Optional[str] = None,
    scan_id: Optional[str] = None,
) -> Dict[str, Any]:
    
    pages = (total + page_size - 1) // page_size if total > 0 else 1
    
    pagination = PaginationMetadata(
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        has_next=page < pages,
        has_previous=page > 1,
    )
    
    metadata_dict = _get_request_metadata()
    
    if request_id:
        metadata_dict["request_id"] = request_id
    
    if scan_id:
        metadata_dict["scan_id"] = scan_id
    
    metadata = ResponseMetadata(**metadata_dict)
    
    response_model = PaginatedResponse(
        data=data,
        pagination=pagination,
        metadata=metadata,
    )
    
    return response_model.model_dump(exclude_none=True)


def health_response(
    status: str,
    version: str,
    uptime_seconds: Optional[float] = None,
    services: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    """
    Specialized health check response for monitoring endpoints.
    
    Example:
    {
        "success": true,
        "status": "healthy",
        "version": "1.0.0",
        "uptime_seconds": 3600,
        "services": {
            "database": true,
            "redis": true
        },
        "timestamp": "2024-01-01T00:00:00Z"
    }
    """
    metadata_dict = _get_request_metadata()
    metadata = ResponseMetadata(**metadata_dict)
    
    response = {
        "success": True,
        "status": status,
        "version": version,
        "metadata": metadata.model_dump(exclude_none=True),
        "timestamp": generate_utc_timestamp(),
    }
    
    if uptime_seconds is not None:
        response["uptime_seconds"] = uptime_seconds
    
    if services is not None:
        response["services"] = services
    
    return response


# ==========================================================
# END OF FILE
# ==========================================================