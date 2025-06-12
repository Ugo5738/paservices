import pytest
from sqlalchemy import text

from auth_service.db import engine


@pytest.mark.asyncio
async def test_db_connection():
    """Test that the database connection can execute a simple query."""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
