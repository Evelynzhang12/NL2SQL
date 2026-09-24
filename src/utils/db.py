"""Database connection management"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import create_engine, Engine

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

_engine: Optional[Engine] = None


def get_db_engine() -> Engine:
    """
    Get or create the database engine with connection pooling.
    
    Returns:
        SQLAlchemy Engine instance
    """
    global _engine
    
    if _engine is None:
        logger.info("Initializing database engine...")
        _engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=settings.DATABASE_POOL_PRE_PING,
            pool_recycle=settings.DATABASE_POOL_RECYCLE,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            echo=False,
        )
        logger.info("Database engine initialized")
    
    return _engine
