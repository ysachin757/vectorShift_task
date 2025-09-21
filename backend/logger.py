import logging
import json
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Union
from contextvars import ContextVar
from models import PipelineRequest, PipelineResponse


# Context variable for request tracking
request_id_context: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


class StructuredLogger:
    """Enhanced structured logging system with JSON output and request tracking"""
    
    def __init__(self, name: str = "vectorshift", level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Create structured formatter
        formatter = StructuredFormatter()
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler for persistent logs
        file_handler = logging.FileHandler("vectorshift.log")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Remove default handlers to avoid duplicate logs
        self.logger.propagate = False
    
    def _create_log_record(
        self, 
        level: str, 
        message: str, 
        extra_data: Optional[Dict[str, Any]] = None,
        category: str = "general"
    ) -> Dict[str, Any]:
        """Create structured log record"""
        record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "message": message,
            "category": category,
            "request_id": request_id_context.get(),
            "service": "vectorshift-backend"
        }
        if extra_data:
            record.update(extra_data)
        return record
    
    def info(self, message: str, extra_data: Optional[Dict[str, Any]] = None, category: str = "general"):
        """Log info message"""
        record = self._create_log_record("INFO", message, extra_data, category)
        self.logger.info(json.dumps(record))
    
    def error(self, message: str, extra_data: Optional[Dict[str, Any]] = None, category: str = "error"):
        """Log error message"""
        record = self._create_log_record("ERROR", message, extra_data, category)
        self.logger.error(json.dumps(record))
    
    def warning(self, message: str, extra_data: Optional[Dict[str, Any]] = None, category: str = "warning"):
        """Log warning message"""
        record = self._create_log_record("WARNING", message, extra_data, category)
        self.logger.warning(json.dumps(record))
    
    def debug(self, message: str, extra_data: Optional[Dict[str, Any]] = None, category: str = "debug"):
        """Log debug message"""
        record = self._create_log_record("DEBUG", message, extra_data, category)
        self.logger.debug(json.dumps(record))
    
    def api_request(self, method: str, path: str, client_ip: str, user_agent: str = None):
        """Log API request"""
        self.info("API request received", {
            "method": method,
            "path": path,
            "client_ip": client_ip,
            "user_agent": user_agent
        }, "api")
    
    def api_response(self, status_code: int, response_time: float, response_size: int = None):
        """Log API response"""
        self.info("API response sent", {
            "status_code": status_code,
            "response_time_ms": round(response_time * 1000, 2),
            "response_size_bytes": response_size
        }, "api")
    
    def validation_start(self, node_count: int, edge_count: int):
        """Log validation start"""
        self.info("Pipeline validation started", {
            "node_count": node_count,
            "edge_count": edge_count,
            "complexity_score": node_count + edge_count * 2
        }, "validation")
    
    def validation_result(self, is_dag: bool, is_pipeline: bool, validation_time: float, 
                         dag_messages: list = None, pipeline_messages: list = None):
        """Log validation result"""
        self.info("Pipeline validation completed", {
            "is_dag": is_dag,
            "is_pipeline": is_pipeline,
            "validation_time_ms": round(validation_time * 1000, 2),
            "dag_message_count": len(dag_messages or []),
            "pipeline_message_count": len(pipeline_messages or []),
            "success": is_dag and is_pipeline
        }, "validation")
    
    def security_event(self, event_type: str, client_ip: str, details: Dict[str, Any] = None):
        """Log security event"""
        event_data = {
            "event_type": event_type,
            "client_ip": client_ip
        }
        if details:
            event_data.update(details)
        self.warning(f"Security event: {event_type}", event_data, "security")
    
    def performance_metric(self, metric_name: str, value: Union[int, float], unit: str = None):
        """Log performance metric"""
        self.info(f"Performance metric: {metric_name}", {
            "metric_name": metric_name,
            "value": value,
            "unit": unit
        }, "performance")
    
    def system_event(self, event: str, details: Dict[str, Any] = None):
        """Log system event"""
        self.info(f"System event: {event}", details or {}, "system")


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging"""
    
    def format(self, record):
        # If the message is already JSON, return as is
        try:
            json.loads(record.getMessage())
            return record.getMessage()
        except (json.JSONDecodeError, TypeError):
            # Create structured log for non-JSON messages
            log_record = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": record.levelname,
                "message": record.getMessage(),
                "logger": record.name,
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno
            }
            return json.dumps(log_record)


class RequestTracker:
    """Utility class for tracking requests across the application"""
    
    @staticmethod
    def generate_request_id() -> str:
        """Generate unique request ID"""
        return str(uuid.uuid4())
    
    @staticmethod
    def set_request_id(request_id: str):
        """Set request ID in context"""
        request_id_context.set(request_id)
    
    @staticmethod
    def get_request_id() -> Optional[str]:
        """Get current request ID"""
        return request_id_context.get()
    
    @staticmethod
    def clear_request_id():
        """Clear request ID from context"""
        request_id_context.set(None)


# Global logger instance
structured_logger = StructuredLogger()


# Enhanced logging function for pipeline operations
def log_to_markdown(request: PipelineRequest, response: PipelineResponse):
    """Log request and response to markdown file (backward compatibility)"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request_json = json.dumps(json.loads(request.json()), indent=2)
    response_json = json.dumps(json.loads(response.json()), indent=2)
    
    log_entry = f"""
## Request at {timestamp}

### Pipeline Request
```json
{request_json}
```

### Pipeline Response
```json
{response_json}
```

---
"""
    with open("pipeline_logs.md", "a", encoding="utf-8") as log_file:
        log_file.write(log_entry)
    
    # Also log to structured logger
    structured_logger.info("Pipeline validation request processed", {
        "request_summary": {
            "node_count": response.num_nodes,
            "edge_count": response.num_edges,
            "is_dag": response.is_dag,
            "is_pipeline": response.is_pipeline
        }
    }, "pipeline")


def log_validation_performance(validation_time: float, node_count: int, edge_count: int):
    """Log validation performance metrics"""
    structured_logger.performance_metric("validation_time", validation_time, "seconds")
    structured_logger.performance_metric("pipeline_complexity", node_count + edge_count * 2, "score")
    
    # Log performance warning if validation is slow
    if validation_time > 1.0:  # More than 1 second
        structured_logger.warning("Slow validation detected", {
            "validation_time": validation_time,
            "node_count": node_count,
            "edge_count": edge_count,
            "suggestion": "Consider optimizing validation logic for large pipelines"
        }, "performance")


def log_error_details(exception: Exception, context: Dict[str, Any] = None):
    """Log detailed error information"""
    import traceback
    
    structured_logger.error(f"Exception occurred: {type(exception).__name__}", {
        "exception_type": type(exception).__name__,
        "exception_message": str(exception),
        "traceback": traceback.format_exc(),
        "context": context or {}
    }, "error")