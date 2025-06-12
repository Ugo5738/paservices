"""
Super ID Service - Main application entry point
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from super_id_service.config import settings
from super_id_service.routers.super_id_router import router as super_id_router
from super_id_service.routers.health_router import router as health_router

# Initialize rate limiter
limiter = Limiter(key_func=lambda _: "global")

# Initialize FastAPI app with root_path from settings
app = FastAPI(
    title="Super ID Service",
    description="Service for generating and recording unique identifiers (UUIDs)",
    version="0.1.0",
    root_path=settings.root_path,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiter middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include routers
app.include_router(health_router)
app.include_router(super_id_router, prefix="/super_ids", tags=["super_ids"])

# Add global exception handler for consistent error responses
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for consistent error responses."""
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": str(type(exc).__name__)},
    )

# Add startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Perform startup actions."""
    pass

@app.on_event("shutdown")
async def shutdown_event():
    """Perform shutdown actions."""
    pass

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run("super_id_service.main:app", host="0.0.0.0", port=8000, reload=True)
