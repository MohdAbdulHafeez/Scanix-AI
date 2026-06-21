# ==========================================================
# SCANIX AI
# CORE - LOGGING
# Structured logging with JSON format for production
# Supports async-safe context variables and request correlation
# ==========================================================


import json
import logging
import os
import re
import sys
from contextvars import ContextVar
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Set

from core.config import settings


# ==========================================================
# CONSTANTS & ASYNC CONTEXT VARIABLES
# ==========================================================


DEFAULT_LOG_LEVEL = "INFO"

ENABLE_JSON_LOGGING_ENV = "ENABLE_JSON_LOGGING"

# PII patterns for redaction (production security)
PII_PATTERNS: List[re.Pattern] = [
    re.compile(r'\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b'),  # Email
    re.compile(r'\\b\\d{10}\\b'),  # Phone (10 digits)
    re.compile(r'(?i)\\b(?:api[_-]?key|apikey|secret|token|password|jwt)\\s*[=:]\\s*[\'"]?\\S+[\'"]?'),  # Keys/secrets
    re.compile(r'\\b[0-9a-fA-F]{32,}\\b'),  # Hex tokens (32+ chars)
    re.compile(r'\\beyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\b'),  # JWT tokens
]

# Context variables ensure correlation IDs stay isolated per async request
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

scan_id_ctx: ContextVar[Optional[str]] = ContextVar("scan_id", default=None)

trace_id_ctx: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)

span_id_ctx: ContextVar[Optional[str]] = ContextVar("span_id", default=None)


# ==========================================================
# PII REDACTION UTILITY
# ==========================================================


def redact_pii(text: str) -> str:
    """
    Redact personally identifiable information and secrets from log messages.
    
    Replaces:
    - Email addresses -> [REDACTED_EMAIL]
    - Phone numbers -> [REDACTED_PHONE]
    - API keys/secrets -> [REDACTED_KEY]
    - Long hex tokens -> [REDACTED_TOKEN]
    - JWTs -> [REDACTED_JWT]
    """
    if not text:
        return text
    
    redacted_text = text
    
    for pattern in PII_PATTERNS:
        redacted_text = pattern.sub(_get_redaction_label(pattern), redacted_text)
    
    return redacted_text


def _get_redaction_label(pattern: re.Pattern) -> str:
    """Return appropriate redaction label based on pattern type"""
    pattern_str = pattern.pattern.lower()
    
    if '@' in pattern_str and '.' in pattern_str:
        return '[REDACTED_EMAIL]'
    elif '\\d{10}' in pattern_str:
        return '[REDACTED_PHONE]'
    elif 'api[_-]?key|apikey|secret|token|password|jwt' in pattern_str:
        return '[REDACTED_KEY]'
    elif 'eyJ' in pattern_str:
        return '[REDACTED_JWT]'
    elif '[0-9a-f]' in pattern_str:
        return '[REDACTED_TOKEN]'
    
    return '[REDACTED]'


# ==========================================================
# LOG SAMPLING CONFIGURATION
# ==========================================================


class LogSampler:
    """Sample log messages to reduce volume in production"""
    
    def __init__(self, sample_rate: float = 1.0):
        self.sample_rate = sample_rate
        self._counter = 0
    
    def should_log(self, level: int) -> bool:
        """Determine if a log message should be sampled"""
        # Always log errors and above
        if level >= logging.ERROR:
            return True
        
        # Sample based on rate
        if self.sample_rate >= 1.0:
            return True
        
        self._counter += 1
        return (self._counter % int(1 / self.sample_rate)) == 0


# Global sampler instance (configured during setup)
_log_sampler: Optional[LogSampler] = None


# ==========================================================
# STRUCTURED JSON FORMATTER
# ==========================================================


class StructuredFormatter(logging.Formatter):
    
    def __init__(
        self,
        include_request_id: bool = True,
        include_scan_id: bool = True,
        include_trace_id: bool = True,
        include_span_id: bool = True,
        redact_pii: bool = True,
    ):
        
        super().__init__()
        
        self.include_request_id = include_request_id
        
        self.include_scan_id = include_scan_id
        
        self.include_trace_id = include_trace_id
        
        self.include_span_id = include_span_id
        
        self.redact_pii = redact_pii
    
    
    def format(self, record: logging.LogRecord) -> str:
        
        # Use record.created for consistent timestamp across formatters
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc)
        
        log_entry: Dict[str, Any] = {
            "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": self._safe_format_message(record),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Merge extra data from adapter
        if hasattr(record, "extra_data") and record.extra_data:
            
            # Redact PII in extra data if enabled
            if self.redact_pii:
                log_entry["extra"] = self._redact_extra_data(record.extra_data)
            else:
                log_entry["extra"] = record.extra_data
        
        # Inject Async Context Variables directly into root JSON payload
        if self.include_request_id:
            
            req_id = request_id_ctx.get()
            
            if req_id:
                
                log_entry["request_id"] = req_id
        
        if self.include_scan_id:
            
            sc_id = scan_id_ctx.get()
            
            if sc_id:
                
                log_entry["scan_id"] = sc_id
        
        if self.include_trace_id:
            
            tr_id = trace_id_ctx.get()
            
            if tr_id:
                
                log_entry["trace_id"] = tr_id
        
        if self.include_span_id:
            
            sp_id = span_id_ctx.get()
            
            if sp_id:
                
                log_entry["span_id"] = sp_id
        
        # Use fast, compact serialization
        return json.dumps(log_entry, separators=(',', ':'))
    
    
    def _safe_format_message(self, record: logging.LogRecord) -> str:
        """Format message with optional PII redaction"""
        message = record.getMessage()
        
        if self.redact_pii:
            return redact_pii(message)
        
        return message
    
    
    def _redact_extra_data(self, extra: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively redact PII from extra data dictionary"""
        if not isinstance(extra, dict):
            return extra
        
        redacted = {}
        
        for key, value in extra.items():
            # Redact sensitive key names
            sensitive_keys = {"email", "phone", "password", "token", "jwt", "api_key", "secret"}
            
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                redacted[key] = "[REDACTED]"
            elif isinstance(value, str):
                redacted[key] = redact_pii(value)
            elif isinstance(value, dict):
                redacted[key] = self._redact_extra_data(value)
            else:
                redacted[key] = value
        
        return redacted


# ==========================================================
# COLORED CONSOLE FORMATTER (Development)
# ==========================================================


class ColoredConsoleFormatter(logging.Formatter):
    
    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
        "RESET": "\033[0m",
    }
    
    def __init__(
        self,
        include_request_id: bool = True,
        include_scan_id: bool = True,
        include_trace_id: bool = False,
        include_span_id: bool = False,
        redact_pii: bool = True,
    ):
        
        super().__init__()
        
        self.include_request_id = include_request_id
        
        self.include_scan_id = include_scan_id
        
        self.include_trace_id = include_trace_id
        
        self.include_span_id = include_span_id
        
        self.redact_pii = redact_pii
    
    
    def format(self, record: logging.LogRecord) -> str:
        
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        
        reset = self.COLORS["RESET"]
        
        # Use record.created for consistency
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        
        message = record.getMessage()
        
        if self.redact_pii:
            message = redact_pii(message)
        
        log_line = f"{color}{timestamp} | {record.levelname:<8} | {record.name:<15} | {reset}{message}"
        
        if self.include_request_id:
            
            req_id = request_id_ctx.get()
            
            if req_id:
                
                log_line += f" | req_id={req_id}"
        
        if self.include_scan_id:
            
            sc_id = scan_id_ctx.get()
            
            if sc_id:
                
                log_line += f" | scan_id={sc_id}"
        
        if self.include_trace_id:
            
            tr_id = trace_id_ctx.get()
            
            if tr_id:
                
                log_line += f" | trace_id={tr_id}"
        
        if self.include_span_id:
            
            sp_id = span_id_ctx.get()
            
            if sp_id:
                
                log_line += f" | span_id={sp_id}"
        
        return log_line


# ==========================================================
# LOGGER ADAPTER
# ==========================================================


class LoggerAdapter(logging.LoggerAdapter):
    
    def __init__(
        self,
        logger: logging.Logger,
        extra: Optional[Dict[str, Any]] = None,
    ):
        
        super().__init__(logger, extra or {})
    
    
    def set_request_id(self, request_id: str) -> None:
        
        request_id_ctx.set(request_id)
    
    
    def set_scan_id(self, scan_id: str) -> None:
        
        scan_id_ctx.set(scan_id)
    
    
    def set_trace_id(self, trace_id: str) -> None:
        
        trace_id_ctx.set(trace_id)
    
    
    def set_span_id(self, span_id: str) -> None:
        
        span_id_ctx.set(span_id)
    
    
    def clear_correlation_ids(self) -> None:
        
        request_id_ctx.set(None)
        
        scan_id_ctx.set(None)
        
        trace_id_ctx.set(None)
        
        span_id_ctx.set(None)
    
    
    def _should_sample(self, level: int) -> bool:
        """Check if this log should be sampled"""
        global _log_sampler
        
        if _log_sampler is None:
            return True
        
        return _log_sampler.should_log(level)
    
    
    def debug(self, msg: Any, *args, **kwargs) -> None:
        """Sampled debug logging"""
        if self.isEnabledFor(logging.DEBUG) and self._should_sample(logging.DEBUG):
            self.log(logging.DEBUG, msg, *args, **kwargs)
    
    
    def info(self, msg: Any, *args, **kwargs) -> None:
        """Sampled info logging"""
        if self.isEnabledFor(logging.INFO) and self._should_sample(logging.INFO):
            self.log(logging.INFO, msg, *args, **kwargs)
    
    
    def warning(self, msg: Any, *args, **kwargs) -> None:
        """Warning logging (always logged)"""
        if self.isEnabledFor(logging.WARNING):
            self.log(logging.WARNING, msg, *args, **kwargs)
    
    
    def error(self, msg: Any, *args, **kwargs) -> None:
        """Error logging (always logged)"""
        if self.isEnabledFor(logging.ERROR):
            self.log(logging.ERROR, msg, *args, **kwargs)
    
    
    def critical(self, msg: Any, *args, **kwargs) -> None:
        """Critical logging (always logged)"""
        if self.isEnabledFor(logging.CRITICAL):
            self.log(logging.CRITICAL, msg, *args, **kwargs)
    
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        
        extra_data = kwargs.pop("extra", {})
        
        # Redact PII in extra data if not already redacted
        if self.redact_pii:
            extra_data = self._redact_extra_data(extra_data)
        
        if self.extra:
            
            combined_extra = {**self.extra, **extra_data}
            
            kwargs["extra"] = {"extra_data": combined_extra}
            
        elif extra_data:
            
            kwargs["extra"] = {"extra_data": extra_data}
        
        return msg, kwargs
    
    
    @property
    def redact_pii(self) -> bool:
        """Check if PII redaction is enabled"""
        return getattr(settings, "LOG_REDACT_PII", True)
    
    
    def _redact_extra_data(self, extra: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively redact PII from extra data"""
        if not isinstance(extra, dict):
            return extra
        
        redacted = {}
        sensitive_keys = {"email", "phone", "password", "token", "jwt", "api_key", "secret"}
        
        for key, value in extra.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                redacted[key] = "[REDACTED]"
            elif isinstance(value, str):
                redacted[key] = redact_pii(value)
            elif isinstance(value, dict):
                redacted[key] = self._redact_extra_data(value)
            else:
                redacted[key] = value
        
        return redacted


# ==========================================================
# SETUP LOGGING
# ==========================================================


def setup_logging() -> None:
    
    global _log_sampler
    
    root_logger = logging.getLogger()
    
    log_level_str = getattr(settings, "LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    
    log_level = getattr(logging, log_level_str, logging.INFO)
    
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to prevent duplication
    for handler in root_logger.handlers[:]:
        
        root_logger.removeHandler(handler)
    
    root_logger.propagate = False
    
    # Determine log format (JSON for production)
    enable_json = False
    
    if hasattr(settings, "ENV") and settings.ENV == "production":
        
        enable_json = True
    
    json_env = os.getenv(ENABLE_JSON_LOGGING_ENV, "").lower()
    
    if json_env == "true":
        
        enable_json = True
        
    elif json_env == "false":
        
        enable_json = False
    
    # Setup log sampling for production
    sample_rate = getattr(settings, "LOG_SAMPLE_RATE", 1.0)
    
    if enable_json and sample_rate < 1.0:
        _log_sampler = LogSampler(sample_rate)
        root_logger.info(f"Log sampling enabled: rate={sample_rate}")
    else:
        _log_sampler = None
    
    # Get PII redaction setting
    redact_pii = getattr(settings, "LOG_REDACT_PII", True)
    
    # Get correlation ID settings
    include_trace_id = getattr(settings, "LOG_INCLUDE_TRACE_ID", False)
    include_span_id = getattr(settings, "LOG_INCLUDE_SPAN_ID", False)
    
    # Configure formatter based on environment
    if enable_json:
        formatter = StructuredFormatter(
            redact_pii=redact_pii,
            include_trace_id=include_trace_id,
            include_span_id=include_span_id,
        )
    else:
        formatter = ColoredConsoleFormatter(
            redact_pii=redact_pii,
            include_trace_id=include_trace_id,
            include_span_id=include_span_id,
        )
    
    handler = logging.StreamHandler(sys.stdout)
    
    handler.setFormatter(formatter)
    
    root_logger.addHandler(handler)
    
    # Intercept Uvicorn and FastAPI loggers to enforce our format
    intercept_loggers = ["uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"]
    
    for logger_name in intercept_loggers:
        
        logger = logging.getLogger(logger_name)
        
        logger.handlers = [handler]
        
        logger.propagate = False
    
    # Log initialization complete
    root_logger.info(
        f"Logging initialized | format={'JSON' if enable_json else 'CONSOLE'} | "
        f"level={log_level_str} | redact_pii={redact_pii} | sample_rate={sample_rate}"
    )


# ==========================================================
# PUBLIC API
# ==========================================================


def get_logger(
    name: str,
    extra: Optional[Dict[str, Any]] = None,
    system: Optional[str] = None,
) -> LoggerAdapter:
    
    logger = logging.getLogger(name)
    
    extra_dict = extra or {}
    
    if system:
        
        extra_dict["system"] = system
    
    return LoggerAdapter(logger, extra_dict)


def get_scan_logger(scan_id: Optional[str] = None) -> LoggerAdapter:
    
    logger = get_logger("scanix.scan", system="scan_intelligence")
    
    if scan_id:
        
        logger.set_scan_id(scan_id)
    
    return logger


def get_api_logger(request_id: Optional[str] = None) -> LoggerAdapter:
    
    logger = get_logger("scanix.api", system="api")
    
    if request_id:
        
        logger.set_request_id(request_id)
    
    return logger


def get_trace_logger(
    request_id: Optional[str] = None,
    scan_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> LoggerAdapter:
    """
    Get logger with full distributed tracing support.
    Use this for complex operations spanning multiple services.
    """
    logger = get_logger("scanix.trace", system="tracing")
    
    if request_id:
        logger.set_request_id(request_id)
    
    if scan_id:
        logger.set_scan_id(scan_id)
    
    if trace_id:
        logger.set_trace_id(trace_id)
    
    return logger


def set_current_request_id(request_id: str) -> None:
    """Set request ID for current async context"""
    request_id_ctx.set(request_id)


def set_current_scan_id(scan_id: str) -> None:
    """Set scan ID for current async context"""
    scan_id_ctx.set(scan_id)


def get_current_request_id() -> Optional[str]:
    """Get current request ID from context"""
    return request_id_ctx.get()


def get_current_scan_id() -> Optional[str]:
    """Get current scan ID from context"""
    return scan_id_ctx.get()


def clear_current_correlation_ids() -> None:
    """Clear all correlation IDs from current context"""
    request_id_ctx.set(None)
    scan_id_ctx.set(None)
    trace_id_ctx.set(None)
    span_id_ctx.set(None)


# ==========================================================
# LIFECYCLE MANAGEMENT
# ==========================================================


def shutdown_logging() -> None:
    """Graceful shutdown for logging system"""
    root_logger = logging.getLogger()
    
    for handler in root_logger.handlers:
        handler.flush()
        handler.close()
    
    logging.shutdown()


# ==========================================================
# INITIALIZATION
# ==========================================================


# Setup logging immediately (can be reconfigured later)
setup_logging()


# ==========================================================
# DEFAULT INSTANCES
# ==========================================================


log = get_logger("scanix")


# ==========================================================
# END OF FILE
# ==========================================================