# super_id_service/src/super_id_service/db.py
from typing import AsyncGenerator

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from super_id_service.config import settings
from super_id_service.utils.logging_config import logger

# Create the async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.LOGGING_LEVEL.upper() == "DEBUG",
    pool_pre_ping=True,
    poolclass=NullPool,
)

# Create a session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# Base class for SQLAlchemy models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency to provide a transactional database session.
    """
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Database transaction failed: {e}", exc_info=True)
        raise
    finally:
        await session.close()
