# src/auth_service/crud/user_crud.py
import logging
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..models.profile import Profile
from ..schemas.user_schemas import ProfileCreate, UserProfileUpdateRequest

logger = logging.getLogger(__name__)


async def get_profile_by_user_id(
    db_session: AsyncSession, user_id: UUID
) -> Profile | None:
    """Retrieves a user profile from the database by user_id."""
    try:
        result = await db_session.execute(
            select(Profile).filter(Profile.user_id == user_id)
        )
        return result.scalars().first()
    except SQLAlchemyError as e:
        logger.error(
            f"Database error while fetching profile for user_id {user_id}: {e}",
            exc_info=True,
        )
        return None


# Keep the old function name as an alias for backwards compatibility
get_profile_by_user_id_from_db = get_profile_by_user_id


async def get_profile_by_username(
    db_session: AsyncSession, username: str
) -> Profile | None:
    """Retrieves a user profile from the database by username."""
    try:
        result = await db_session.execute(
            select(Profile).filter(Profile.username == username)
        )
        return result.scalars().first()
    except SQLAlchemyError as e:
        logger.error(
            f"Database error while fetching profile for username {username}: {e}",
            exc_info=True,
        )
        return None


async def create_profile_in_db(
    db_session: AsyncSession, profile_in: ProfileCreate
) -> Profile | None:
    """Creates a new user profile in the database."""
    try:
        new_profile = Profile(**profile_in.model_dump())
        db_session.add(new_profile)
        # The calling function or dependency manager is responsible for the commit.
        # We flush to get the ID back before the transaction ends.
        await db_session.flush()
        await db_session.refresh(new_profile)
        logger.info(f"Profile created successfully for user_id: {new_profile.user_id}")
        return new_profile
    except SQLAlchemyError as e:
        logger.error(
            f"Database error during profile creation for user_id {profile_in.user_id}: {e}",
            exc_info=True,
        )
        await db_session.rollback()
        return None


async def get_profile_by_email(
    db_session: AsyncSession, email: str
) -> Profile | None:
    """Retrieves a user profile from the database by email."""
    try:
        result = await db_session.execute(
            select(Profile).filter(Profile.email == email)
        )
        return result.scalars().first()
    except SQLAlchemyError as e:
        logger.error(
            f"Database error while fetching profile for email {email}: {e}",
            exc_info=True,
        )
        return None


async def update_profile(
    db_session: AsyncSession, profile: Profile, update_data: dict
) -> Profile | None:
    """Updates a user profile in the database."""
    try:
        for key, value in update_data.items():
            if hasattr(profile, key) and value is not None:
                setattr(profile, key, value)
                
        await db_session.flush()
        await db_session.refresh(profile)
        logger.info(f"Profile updated successfully for user_id: {profile.user_id}")
        return profile
    except SQLAlchemyError as e:
        logger.error(
            f"Database error during profile update for user_id {profile.user_id}: {e}",
            exc_info=True,
        )
        await db_session.rollback()
        return None


async def deactivate_profile(
    db_session: AsyncSession, user_id: UUID
) -> Profile | None:
    """Deactivates a user profile by setting is_active to False."""
    try:
        profile = await get_profile_by_user_id(db_session, user_id)
        if not profile:
            return None
            
        profile.is_active = False
        await db_session.flush()
        await db_session.refresh(profile)
        logger.info(f"Profile deactivated successfully for user_id: {profile.user_id}")
        return profile
    except SQLAlchemyError as e:
        logger.error(
            f"Database error during profile deactivation for user_id {user_id}: {e}",
            exc_info=True,
        )
        await db_session.rollback()
        return None
