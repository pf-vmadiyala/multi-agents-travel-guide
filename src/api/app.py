import time
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from src.api.routes import router
from src.utils.errors import APIError
from src.utils.metrics import api_requests_total, api_request_duration_seconds

# Initialize FastAPI application
app = FastAPI(
    title="Multi-Agent Travel Planner API",
    description="REST API backend for the distributed LangGraph travel planning system.",
    version="1.0.0"
)

# Enable CORS for frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware to track request count and latency
@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    """Record request count and latency metrics for non-health/metrics endpoints."""
    path = request.url.path
    # Skip tracking for metrics and health probes to avoid metric pollution
    if path in ("/metrics", "/api/v1/health/live", "/api/v1/health/ready", "/"):
        return await call_next(request)
        
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    # Record metrics
    api_requests_total.labels(
        endpoint=path,
        method=request.method,
        status=response.status_code
    ).inc()
    
    api_request_duration_seconds.labels(
        endpoint=path
    ).observe(duration)
    
    return response

# Register the global custom API exception handler
@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    """
    Catches all custom application errors and returns a standardized JSON structure
    with the appropriate HTTP status code.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message
        }
    )

from fastapi.staticfiles import StaticFiles

# Expose /metrics endpoint for Prometheus scraping
@app.get("/metrics")
async def get_metrics():
    """Expose Prometheus metrics in the standard text exposition format."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Include API endpoints under /api/v1 prefix
app.include_router(router, prefix="/api/v1")

# Mount the static files UI directory at root path
app.mount("/", StaticFiles(directory="src/static", html=True), name="static")
