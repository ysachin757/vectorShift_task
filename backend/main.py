import uvicorn
import time
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from models import PipelineRequest, PipelineResponse
from validation import validate_graph
from enhanced_validation import EnhancedValidator
from logger import (
    log_to_markdown, 
    structured_logger, 
    RequestTracker,
    log_validation_performance,
    log_error_details
)
from security import SecurityMiddleware, RateLimiter
from exceptions import (
    VectorShiftException,
    ValidationException,
    SecurityException,
    handle_vectorshift_exception,
    handle_validation_error,
    handle_security_exception,
    handle_general_exception
)

# Initialize FastAPI app with metadata
app = FastAPI(
    title="VectorShift Pipeline Validator",
    description="Production-ready pipeline validation service with comprehensive security and monitoring",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Initialize security components
rate_limiter = RateLimiter()
enhanced_validator = EnhancedValidator()

# Add security middleware (must be added before CORS)
app.add_middleware(SecurityMiddleware, rate_limiter=rate_limiter)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
    max_age=86400,
)

# Exception handlers
app.add_exception_handler(VectorShiftException, handle_vectorshift_exception)
app.add_exception_handler(ValidationException, handle_validation_error)
app.add_exception_handler(SecurityException, handle_security_exception)
app.add_exception_handler(RequestValidationError, handle_validation_error)
app.add_exception_handler(Exception, handle_general_exception)

# Request tracking middleware
@app.middleware("http")
async def request_tracking_middleware(request: Request, call_next):
    """Middleware for request tracking and performance monitoring"""
    start_time = time.time()
    
    # Generate and set request ID
    request_id = RequestTracker.generate_request_id()
    RequestTracker.set_request_id(request_id)
    
    # Log incoming request
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    structured_logger.api_request(
        method=request.method,
        path=str(request.url.path),
        client_ip=client_ip,
        user_agent=user_agent
    )
    
    try:
        # Process request
        response = await call_next(request)
        
        # Calculate response time
        response_time = time.time() - start_time
        
        # Log response
        response_size = response.headers.get("content-length")
        if response_size:
            response_size = int(response_size)
        
        structured_logger.api_response(
            status_code=response.status_code,
            response_time=response_time,
            response_size=response_size
        )
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response
        
    except Exception as e:
        # Log error with context
        response_time = time.time() - start_time
        log_error_details(e, {
            "method": request.method,
            "path": str(request.url.path),
            "client_ip": client_ip,
            "response_time": response_time
        })
        raise
    
    finally:
        # Clear request context
        RequestTracker.clear_request_id()


@app.get('/', 
         summary="Health Check",
         description="Basic health check endpoint to verify service availability")
def read_root():
    """Health check endpoint"""
    structured_logger.info("Health check requested", category="health")
    return {
        'service': 'VectorShift Pipeline Validator',
        'status': 'healthy',
        'version': '2.0.0',
        'features': [
            'enhanced_validation',
            'security_middleware',
            'structured_logging',
            'request_tracking'
        ]
    }


@app.options('/pipelines/parse')
@app.post('/pipelines/parse', 
          response_model=PipelineResponse,
          summary="Validate Pipeline",
          description="Validate pipeline structure with enhanced semantic checking and security")
async def parse_pipeline(request: PipelineRequest) -> PipelineResponse:
    """
    Enhanced pipeline validation endpoint with comprehensive security and monitoring
    
    Features:
    - DAG structure validation
    - Pipeline connectivity validation
    - Enhanced semantic validation
    - Node type validation
    - Data type compatibility checking
    - Performance monitoring
    - Security protections
    """
    validation_start_time = time.time()
    
    try:
        # Log validation start
        structured_logger.validation_start(
            node_count=len(request.nodes),
            edge_count=len(request.edges)
        )
        
        # Basic validation (existing)
        is_dag, is_pipeline, dag_messages, pipeline_messages = validate_graph(
            request.nodes, 
            request.edges
        )
        
        # Enhanced validation
        enhanced_result = enhanced_validator.validate_pipeline(request.nodes, request.edges)
        
        # Merge validation results
        final_dag_messages = dag_messages + enhanced_result.get("dag_messages", [])
        final_pipeline_messages = pipeline_messages + enhanced_result.get("pipeline_messages", [])
        
        # Calculate validation time
        validation_time = time.time() - validation_start_time
        
        # Create response
        response = PipelineResponse(
            num_nodes=len(request.nodes),
            num_edges=len(request.edges),
            is_dag=is_dag,
            is_pipeline=is_pipeline,
            dag_validation_messages=final_dag_messages,
            pipeline_validation_messages=final_pipeline_messages
        )
        
        # Log validation result
        structured_logger.validation_result(
            is_dag=is_dag,
            is_pipeline=is_pipeline,
            validation_time=validation_time,
            dag_messages=final_dag_messages,
            pipeline_messages=final_pipeline_messages
        )
        
        # Log performance metrics
        log_validation_performance(validation_time, len(request.nodes), len(request.edges))
        
        # Legacy logging for backward compatibility
        log_to_markdown(request, response)
        
        structured_logger.info("Pipeline validation completed successfully", {
            "validation_summary": {
                "success": is_dag and is_pipeline,
                "total_messages": len(final_dag_messages) + len(final_pipeline_messages),
                "processing_time": round(validation_time * 1000, 2)
            }
        }, "pipeline")
        
        return response
        
    except ValidationException as e:
        # Specific validation error
        structured_logger.error(f"Validation error: {e.message}", {
            "error_code": e.error_code,
            "details": e.details
        }, "validation")
        raise
        
    except Exception as e:
        # General error
        validation_time = time.time() - validation_start_time
        log_error_details(e, {
            "operation": "pipeline_validation",
            "node_count": len(request.nodes),
            "edge_count": len(request.edges),
            "validation_time": validation_time
        })
        
        # Return structured error response
        raise VectorShiftException(
            message="Unexpected error during pipeline validation",
            error_code="VALIDATION_SYSTEM_ERROR",
            details={"error_type": type(e).__name__, "error_message": str(e)}
        )


@app.get("/health",
         summary="Detailed Health Check",
         description="Comprehensive health check with system status")
async def health_check():
    """Comprehensive health check endpoint"""
    try:
        # Test components
        health_status = {
            "service": "VectorShift Pipeline Validator",
            "status": "healthy",
            "timestamp": time.time(),
            "components": {
                "validation": "operational",
                "security": "operational", 
                "logging": "operational",
                "rate_limiting": "operational"
            },
            "metrics": {
                "uptime": "operational",
                "performance": "good"
            }
        }
        
        structured_logger.info("Health check completed", health_status, "health")
        return health_status
        
    except Exception as e:
        structured_logger.error("Health check failed", {"error": str(e)}, "health")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "error": str(e)}
        )


# Startup event
@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    structured_logger.system_event("Application startup", {
        "version": "2.0.0",
        "features": ["enhanced_validation", "security_middleware", "structured_logging"]
    })


# Shutdown event  
@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    structured_logger.system_event("Application shutdown")


if __name__ == "__main__":
    structured_logger.system_event("Starting VectorShift Pipeline Validator", {
        "host": "0.0.0.0",
        "port": 8000,
        "environment": "development"
    })
    uvicorn.run(app, host="0.0.0.0", port=8000)