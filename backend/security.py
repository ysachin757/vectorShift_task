from typing import Dict, Optional, Any
from fastapi import Request, Response, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
import time
import json
import re
from collections import defaultdict, deque
from exceptions import (
    SecurityException, 
    RateLimitExceededException,
    RequestTooLargeException,
    ErrorCode
)


class RateLimiter:
    """Sliding window rate limiter"""
    
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, deque] = defaultdict(deque)
    
    def is_allowed(self, client_id: str) -> tuple[bool, int]:
        """
        Check if request is allowed for client
        Returns: (is_allowed, current_request_count)
        """
        now = time.time()
        client_requests = self.requests[client_id]
        
        # Remove old requests outside the window
        while client_requests and client_requests[0] <= now - self.window_seconds:
            client_requests.popleft()
        
        current_count = len(client_requests)
        
        if current_count >= self.max_requests:
            return False, current_count
        
        # Add current request
        client_requests.append(now)
        return True, current_count + 1
    
    def get_reset_time(self, client_id: str) -> int:
        """Get time until rate limit resets"""
        client_requests = self.requests[client_id]
        if not client_requests:
            return 0
        
        oldest_request = client_requests[0]
        reset_time = int(oldest_request + self.window_seconds - time.time())
        return max(0, reset_time)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for rate limiting, input validation, and size limits"""
    
    def __init__(
        self,
        app,
        rate_limit_requests: int = 60,
        rate_limit_window: int = 60,
        max_request_size: int = 10 * 1024 * 1024,  # 10MB
        enable_rate_limiting: bool = True,
        enable_size_checking: bool = True,
        enable_input_sanitization: bool = True
    ):
        super().__init__(app)
        self.rate_limiter = RateLimiter(rate_limit_requests, rate_limit_window)
        self.max_request_size = max_request_size
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_size_checking = enable_size_checking
        self.enable_input_sanitization = enable_input_sanitization
        
        # Patterns for input sanitization
        self.dangerous_patterns = [
            r'<script[^>]*>.*?</script>',  # Script tags
            r'javascript:',                # JavaScript URLs
            r'on\w+\s*=',                 # Event handlers
            r'eval\s*\(',                 # eval() calls
            r'exec\s*\(',                 # exec() calls
        ]
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE | re.DOTALL) 
                                 for pattern in self.dangerous_patterns]
    
    async def dispatch(self, request: Request, call_next):
        """Main middleware processing"""
        start_time = time.time()
        client_ip = self._get_client_ip(request)
        
        try:
            # 1. Rate limiting check
            if self.enable_rate_limiting and self._should_rate_limit(request):
                await self._check_rate_limit(client_ip)
            
            # 2. Request size check
            if self.enable_size_checking:
                await self._check_request_size(request)
            
            # 3. Input sanitization
            if self.enable_input_sanitization:
                await self._sanitize_input(request)
            
            # Process the request
            response = await call_next(request)
            
            # Add security headers
            self._add_security_headers(response)
            
            # Add performance headers
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except SecurityException as e:
            # Convert security exceptions to HTTP responses
            response = Response(
                content=json.dumps(e.to_response().dict()),
                status_code=e.status_code,
                media_type="application/json"
            )
            self._add_security_headers(response)
            return response
        
        except Exception as e:
            # Handle unexpected errors
            response = Response(
                content=json.dumps({
                    "success": False,
                    "error": {
                        "code": ErrorCode.INTERNAL_SERVER_ERROR,
                        "message": "Internal server error"
                    },
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                }),
                status_code=500,
                media_type="application/json"
            )
            self._add_security_headers(response)
            return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address"""
        # Check for forwarded headers first (for proxy setups)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return getattr(request.client, "host", "unknown")
    
    def _should_rate_limit(self, request: Request) -> bool:
        """Determine if request should be rate limited"""
        # Skip rate limiting for health checks
        if request.url.path in ["/", "/health", "/metrics"]:
            return False
        
        # Only rate limit POST requests (API calls)
        return request.method in ["POST", "PUT", "DELETE"]
    
    async def _check_rate_limit(self, client_ip: str) -> None:
        """Check and enforce rate limits"""
        is_allowed, current_count = self.rate_limiter.is_allowed(client_ip)
        
        if not is_allowed:
            reset_time = self.rate_limiter.get_reset_time(client_ip)
            raise RateLimitExceededException(
                limit=self.rate_limiter.max_requests,
                window=self.rate_limiter.window_seconds,
                current_requests=current_count
            )
    
    async def _check_request_size(self, request: Request) -> None:
        """Check request payload size"""
        content_length = request.headers.get("content-length")
        
        if content_length:
            size = int(content_length)
            if size > self.max_request_size:
                raise RequestTooLargeException(size, self.max_request_size)
    
    async def _sanitize_input(self, request: Request) -> None:
        """Sanitize request input for security threats"""
        # Only check JSON requests
        content_type = request.headers.get("content-type", "")
        if "application/json" not in content_type:
            return
        
        try:
            # Read and check request body
            body = await request.body()
            if body:
                body_str = body.decode("utf-8")
                
                # Check for dangerous patterns
                for pattern in self.compiled_patterns:
                    if pattern.search(body_str):
                        raise SecurityException(
                            "Request contains potentially dangerous content",
                            ErrorCode.INVALID_INPUT_FORMAT,
                            details={"pattern_matched": pattern.pattern}
                        )
                
                # Additional JSON-specific checks
                try:
                    data = json.loads(body_str)
                    self._check_json_data(data)
                except json.JSONDecodeError:
                    raise SecurityException(
                        "Invalid JSON format",
                        ErrorCode.INVALID_INPUT_FORMAT
                    )
                
        except UnicodeDecodeError:
            raise SecurityException(
                "Invalid character encoding",
                ErrorCode.INVALID_INPUT_FORMAT
            )
    
    def _check_json_data(self, data: Any, depth: int = 0) -> None:
        """Recursively check JSON data for security issues"""
        max_depth = 10
        max_string_length = 10000
        max_array_length = 1000
        
        if depth > max_depth:
            raise SecurityException(
                f"JSON structure too deeply nested (max depth: {max_depth})",
                ErrorCode.INVALID_INPUT_FORMAT
            )
        
        if isinstance(data, dict):
            if len(data) > 100:  # Limit object size
                raise SecurityException(
                    "JSON object has too many properties",
                    ErrorCode.INVALID_INPUT_FORMAT
                )
            
            for key, value in data.items():
                if isinstance(key, str) and len(key) > 100:
                    raise SecurityException(
                        "JSON property name too long",
                        ErrorCode.INVALID_INPUT_FORMAT
                    )
                self._check_json_data(value, depth + 1)
        
        elif isinstance(data, list):
            if len(data) > max_array_length:
                raise SecurityException(
                    f"JSON array too large (max length: {max_array_length})",
                    ErrorCode.INVALID_INPUT_FORMAT
                )
            
            for item in data:
                self._check_json_data(item, depth + 1)
        
        elif isinstance(data, str):
            if len(data) > max_string_length:
                raise SecurityException(
                    f"JSON string too long (max length: {max_string_length})",
                    ErrorCode.INVALID_INPUT_FORMAT
                )
    
    def _add_security_headers(self, response: Response) -> None:
        """Add security headers to response"""
        response.headers.update({
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains"
        })


class InputValidator:
    """Utility class for additional input validation"""
    
    @staticmethod
    def validate_node_id(node_id: str) -> bool:
        """Validate node ID format"""
        if not isinstance(node_id, str):
            return False
        
        # Allow alphanumeric, dash, underscore
        pattern = r'^[a-zA-Z0-9_-]+$'
        return bool(re.match(pattern, node_id)) and len(node_id) <= 100
    
    @staticmethod
    def validate_node_type(node_type: str) -> bool:
        """Validate node type format"""
        if not isinstance(node_type, str):
            return False
        
        # Allow lowercase letters only
        pattern = r'^[a-z]+$'
        return bool(re.match(pattern, node_type)) and len(node_type) <= 50
    
    @staticmethod
    def sanitize_string(text: str, max_length: int = 1000) -> str:
        """Sanitize string input"""
        if not isinstance(text, str):
            return str(text)[:max_length]
        
        # Remove null bytes and control characters
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        
        # Limit length
        return sanitized[:max_length]
    
    @staticmethod
    def validate_pipeline_data(pipeline_data: Dict[str, Any]) -> bool:
        """Validate pipeline data structure"""
        required_fields = ["nodes", "edges"]
        
        for field in required_fields:
            if field not in pipeline_data:
                return False
        
        nodes = pipeline_data.get("nodes", [])
        edges = pipeline_data.get("edges", [])
        
        if not isinstance(nodes, list) or not isinstance(edges, list):
            return False
        
        # Reasonable limits
        if len(nodes) > 1000 or len(edges) > 2000:
            return False
        
        return True


# Configuration for different environments
SECURITY_CONFIGS = {
    "development": {
        "rate_limit_requests": 120,
        "rate_limit_window": 60,
        "max_request_size": 50 * 1024 * 1024,  # 50MB for dev
        "enable_rate_limiting": False,  # Disabled in dev
        "enable_size_checking": True,
        "enable_input_sanitization": True
    },
    "production": {
        "rate_limit_requests": 60,
        "rate_limit_window": 60,
        "max_request_size": 10 * 1024 * 1024,  # 10MB for prod
        "enable_rate_limiting": True,
        "enable_size_checking": True,
        "enable_input_sanitization": True
    }
}
