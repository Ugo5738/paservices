# super_id_service/src/super_id_service/crud/super_id_crud.py

import uuid
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.generated_super_id import GeneratedSuperID
from ..utils.logging_config import logger


async def create_and_store_super_id(
    db: AsyncSession, *, user_id: str, metadata: Dict[str, Any] | None = None
) -> GeneratedSuperID:
    """
    Creates a new GeneratedSuperID record and adds it to the database session.

    Note: This function does NOT commit the transaction. The session management
    (commit, rollback) is handled by the caller (the tool or API route).

    Args:
        db: The SQLAlchemy async session.
        user_id: The ID of the authenticated user requesting the ID.
        metadata: Optional metadata to store with the ID.

    Returns:
        The newly created GeneratedSuperID object.
    """
    try:
        # Create a list of database model instances
        db_record = GeneratedSuperID(
            super_id=uuid.uuid4(),
            requested_by_client_id=user_id,
            super_id_metadata=metadata,
        )

        # Add all new records to the session in one go
        db.add(db_record)

        # Flush the session to assign a database-side default like 'id' or 'generated_at'
        # to the db_record object before we return it.
        await db.flush()
        await db.refresh(db_record)

        logger.info(
            f"Prepared super_id {db_record.super_id} for user {user_id} for commit."
        )

        return db_record

    except Exception as e:
        logger.error(
            f"Error creating super_id in CRUD layer for user '{user_id}': {e}",
            exc_info=True,
        )
        # Re-raise the exception so the calling function's transaction is rolled back.
        raise
