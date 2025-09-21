from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from pydantic import BaseModel
import traceback
import time


class ErrorCode:
    """Standardized error codes for the API"""
    
    # Validation errors (1000-1999)
    VALIDATION_FAILED = 1000
    INVALID_NODE_TYPE = 1001
    INVALID_EDGE_CONNECTION = 1002
    CYCLE_DETECTED = 1003
    INCOMPLETE_PIPELINE = 1004
    DATA_TYPE_MISMATCH = 1005
    MISSING_REQUIRED_FIELD = 1006
    INVALID_NODE_CONFIGURATION = 1007
    
    # Security errors (2000-2999)
    RATE_LIMIT_EXCEEDED = 2000
    REQUEST_TOO_LARGE = 2001
    INVALID_INPUT_FORMAT = 2002
    UNAUTHORIZED_ACCESS = 2003
    
    # System errors (3000-3999)
    INTERNAL_SERVER_ERROR = 3000
    SERVICE_UNAVAILABLE = 3001
    DATABASE_ERROR = 3002
    TIMEOUT_ERROR = 3003


class ErrorDetail(BaseModel):
    """Detailed error information"""
    code: int
    message: str
    field: Optional[str] = None
    value: Optional[Any] = None
    suggestion: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standardized error response format"""
    success: bool = False
    error: ErrorDetail
    timestamp: str
    request_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class VectorShiftException(Exception):
    """Base exception class for VectorShift API"""
    
    def __init__(
        self,
        message: str,
        error_code: int,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        suggestion: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.field = field
        self.value = value
        self.suggestion = suggestion
        self.details = details or {}
        super().__init__(message)
    
    def to_response(self, request_id: Optional[str] = None) -> ErrorResponse:
        """Convert exception to standardized error response"""
        return ErrorResponse(
            error=ErrorDetail(
                code=self.error_code,
                message=self.message,
                field=self.field,
                value=self.value,
                suggestion=self.suggestion
            ),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            request_id=request_id,
            details=self.details if self.details else None
        )


class ValidationException(VectorShiftException):
    """Exception for validation errors"""
    
    def __init__(
        self,
        message: str,
        error_code: int = ErrorCode.VALIDATION_FAILED,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        suggestion: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            field=field,
            value=value,
            suggestion=suggestion,
            details=details
        )


class SecurityException(VectorShiftException):
    """Exception for security-related errors"""
    
    def __init__(
        self,
        message: str,
        error_code: int = ErrorCode.RATE_LIMIT_EXCEEDED,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS if error_code == ErrorCode.RATE_LIMIT_EXCEEDED else status.HTTP_400_BAD_REQUEST,
            details=details
        )


class SystemException(VectorShiftException):
    """Exception for system-level errors"""
    
    def __init__(
        self,
        message: str,
        error_code: int = ErrorCode.INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details
        )


# Specific validation exceptions for common cases
class InvalidNodeTypeException(ValidationException):
    def __init__(self, node_type: str, valid_types: List[str]):
        super().__init__(
            message=f"Invalid node type: '{node_type}'",
            error_code=ErrorCode.INVALID_NODE_TYPE,
            field="nodeType",
            value=node_type,
            suggestion=f"Valid node types are: {', '.join(valid_types)}",
            details={"valid_types": valid_types}
        )


class CycleDetectedException(ValidationException):
    def __init__(self, cycle_description: str, affected_nodes: List[str]):
        super().__init__(
            message=f"Cycle detected in pipeline: {cycle_description}",
            error_code=ErrorCode.CYCLE_DETECTED,
            suggestion="Remove connections that create cycles to make the pipeline a valid DAG",
            details={"affected_nodes": affected_nodes, "cycle_type": cycle_description}
        )


class DataTypeMismatchException(ValidationException):
    def __init__(self, source_node: str, target_node: str, source_type: str, target_type: str):
        super().__init__(
            message=f"Data type mismatch: {source_node} outputs '{source_type}' but {target_node} expects '{target_type}'",
            error_code=ErrorCode.DATA_TYPE_MISMATCH,
            suggestion=f"Ensure output type '{source_type}' is compatible with input type '{target_type}'",
            details={
                "source_node": source_node,
                "target_node": target_node,
                "source_type": source_type,
                "target_type": target_type
            }
        )


class IncompletePipelineException(ValidationException):
    def __init__(self, missing_connections: List[Dict[str, str]]):
        super().__init__(
            message="Pipeline is incomplete: some required inputs are not connected",
            error_code=ErrorCode.INCOMPLETE_PIPELINE,
            suggestion="Connect all required node inputs to complete the pipeline",
            details={"missing_connections": missing_connections}
        )


class RateLimitExceededException(SecurityException):
    def __init__(self, limit: int, window: int, current_requests: int):
        super().__init__(
            message=f"Rate limit exceeded: {current_requests} requests in {window} seconds (limit: {limit})",
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            details={
                "limit": limit,
                "window_seconds": window,
                "current_requests": current_requests,
                "retry_after": window
            }
        )


class RequestTooLargeException(SecurityException):
    def __init__(self, size: int, max_size: int):
        super().__init__(
            message=f"Request payload too large: {size} bytes (maximum: {max_size} bytes)",
            error_code=ErrorCode.REQUEST_TOO_LARGE,
            details={"size_bytes": size, "max_size_bytes": max_size}
        )


def create_error_response(
    exception: Exception,
    request_id: Optional[str] = None,
    include_traceback: bool = False
) -> ErrorResponse:
    """Create standardized error response from any exception"""
    
    if isinstance(exception, VectorShiftException):
        return exception.to_response(request_id)
    
    # Handle FastAPI HTTPException
    if isinstance(exception, HTTPException):
        return ErrorResponse(
            error=ErrorDetail(
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                message=exception.detail if isinstance(exception.detail, str) else str(exception.detail)
            ),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            request_id=request_id
        )
    
    # Handle unexpected exceptions
    details = {"exception_type": type(exception).__name__}
    if include_traceback:
        details["traceback"] = traceback.format_exc()
    
    return ErrorResponse(
        error=ErrorDetail(
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            message=f"Internal server error: {str(exception)}"
        ),
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        request_id=request_id,
        details=details
    )


# FastAPI Exception Handlers
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


async def handle_vectorshift_exception(request: Request, exc: VectorShiftException):
    """Handle VectorShift custom exceptions"""
    from logger import RequestTracker
    request_id = RequestTracker.get_request_id()
    error_response = exc.to_response(request_id)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.dict()
    )


async def handle_validation_error(request: Request, exc: RequestValidationError):
    """Handle FastAPI validation errors"""
    from logger import RequestTracker
    request_id = RequestTracker.get_request_id()
    
    validation_exception = ValidationException(
        message="Request validation failed",
        details={"validation_errors": exc.errors()}
    )
    error_response = validation_exception.to_response(request_id)
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.dict()
    )


async def handle_security_exception(request: Request, exc: SecurityException):
    """Handle security-related exceptions"""
    from logger import RequestTracker
    request_id = RequestTracker.get_request_id()
    error_response = exc.to_response(request_id)
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.dict()
    )


async def handle_general_exception(request: Request, exc: Exception):
    """Handle all other unexpected exceptions"""
    from logger import RequestTracker, structured_logger
    request_id = RequestTracker.get_request_id()
    
    # Log the unexpected exception
    structured_logger.error(f"Unhandled exception: {type(exc).__name__}", {
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "traceback": traceback.format_exc(),
        "request_path": str(request.url.path),
        "request_method": request.method
    }, "error")
    
    # Create generic error response
    error_response = create_error_response(exc, request_id, include_traceback=False)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.dict()
    )
