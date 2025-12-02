from typing import AsyncGenerator

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from .config import settings
from .utils.logging_config import logger

# Async engine and session factory
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.LOGGING_LEVEL.upper() == "DEBUG",
    pool_pre_ping=True,
    poolclass=NullPool,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional DB session (FastAPI dependency style)."""
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except SQLAlchemyError as exc:
        await session.rollback()
        logger.error("Database transaction failed: %s", exc, exc_info=True)
        raise
    finally:
        await session.close()
