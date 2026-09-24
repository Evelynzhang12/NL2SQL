"""FastAPI application factory"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.api.endpoints import router
from src.utils.logger import get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        Configured FastAPI instance
    """
    logger.info("Initializing FastAPI application...")
    
    app = FastAPI(
        title=settings.API_TITLE,
        version=settings.API_VERSION,
        description="Natural Language to SQL Backend for Financial Data",
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(router)
    
    # Root endpoint for backward compatibility
    @app.get("/")
    def root():
        """Root endpoint - check if service is running"""
        return {"message": "NL2SQL backend is running."}
    
    logger.info("FastAPI application initialized successfully")
    
    return app


# Create application instance
app = create_app()
