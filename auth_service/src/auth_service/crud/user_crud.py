# src/auth_service/crud/user_crud.py
import logging
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..models.profile import Profile
from ..schemas.user_schemas import ProfileCreate, ProfileUpdate

logger = logging.getLogger(__name__)


async def get_profile_by_user_id_from_db(
    db_session: AsyncSession, user_id: UUID
) -> Profile | None:
    """
    Retrieves a user profile from the database by user_id.

    Args:
        db_session: The asynchronous database session.
        user_id: The UUID of the user.

    Returns:
        The Profile object if found, otherwise None.
    """
    try:
        result = await db_session.execute(
            select(Profile).filter(Profile.user_id == user_id)
        )
        profile = result.scalars().first()
        if profile:
            logger.info(f"Profile found for user_id: {user_id}")
        else:
            logger.info(f"No profile found for user_id: {user_id}")
        return profile
    except SQLAlchemyError as e:
        logger.error(
            f"Database error while fetching profile for user_id {user_id}: {e}",
            exc_info=True,
        )
        # Depending on desired error handling, could raise or return None
        return None
    except Exception as e:
        logger.error(
            f"Unexpected error while fetching profile for user_id {user_id}: {e}",
            exc_info=True,
        )
        # Depending on desired error handling, could raise or return None
        return None


async def get_profile_by_username(
    db_session: AsyncSession, username: str
) -> Profile | None:
    """
    Retrieves a user profile from the database by username.

    Args:
        db_session: The asynchronous database session.
        username: The username to search for.

    Returns:
        The Profile object if found, otherwise None.
    """
    try:
        result = await db_session.execute(
            select(Profile).filter(Profile.username == username)
        )
        profile = result.scalars().first()
        if profile:
            logger.info(f"Profile found for username: {username}")
        else:
            logger.info(f"No profile found for username: {username}")
        return profile
    except SQLAlchemyError as e:
        logger.error(
            f"Database error while fetching profile for username {username}: {e}",
            exc_info=True,
        )
        return None
    except Exception as e:
        logger.error(
            f"Unexpected error while fetching profile for username {username}: {e}",
            exc_info=True,
        )
        return None


async def create_profile_in_db(
    db_session: AsyncSession, profile_in: ProfileCreate
) -> Profile | None:
    logger.info(
        f"DEBUG crud.create_profile_in_db: profile_in.email='{profile_in.email}', type='{type(profile_in.email)}'"
    )
    """
    Creates a new user profile in the database.

    Args:
        db_session: The asynchronous database session.
        profile_in: The Pydantic model containing profile creation data.

    Returns:
        The created Profile object if successful, otherwise None.
    """
    try:
        # Ensure user_id is a UUID object if it's passed as a string
        user_id_as_uuid = (
            UUID(str(profile_in.user_id))
            if not isinstance(profile_in.user_id, UUID)
            else profile_in.user_id
        )

        new_profile = Profile(
            user_id=user_id_as_uuid,
            username=profile_in.username,
            email=profile_in.email,
            first_name=profile_in.first_name,
            last_name=profile_in.last_name,
        )
        logger.info(
            f"DEBUG crud.create_profile_in_db: new_profile.email='{new_profile.email}', type='{type(new_profile.email)}' BEFORE add"
        )
        db_session.add(new_profile)
        await db_session.commit()
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
    except Exception as e:
        logger.error(
            f"Unexpected error during profile creation for user_id {profile_in.user_id}: {e}",
            exc_info=True,
        )
        await db_session.rollback()
        return None


async def update_profile_in_db(
    db_session: AsyncSession, profile_id: UUID, profile_in: ProfileUpdate
) -> Profile | None:
    """
    Updates an existing user profile in the database.

    Args:
        db_session: The asynchronous database session.
        profile_id: The UUID of the profile to update.
        profile_in: The Pydantic model containing profile update data.

    Returns:
        The updated Profile object if successful, otherwise None.
    """
    try:
        result = await db_session.execute(
            select(Profile).filter(
                Profile.id == profile_id
            )  # Assuming Profile has an 'id' primary key
        )
        existing_profile = result.scalars().first()

        if not existing_profile:
            logger.warning(f"Profile with id {profile_id} not found for update.")
            return None

        update_data = profile_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(existing_profile, key, value)

        await db_session.commit()
        await db_session.refresh(existing_profile)
        logger.info(f"Profile with id {profile_id} updated successfully.")
        return existing_profile
    except SQLAlchemyError as e:
        logger.error(
            f"Database error during profile update for profile_id {profile_id}: {e}",
            exc_info=True,
        )
        await db_session.rollback()
        return None
    except Exception as e:
        logger.error(
            f"Unexpected error during profile update for profile_id {profile_id}: {e}",
            exc_info=True,
        )
        await db_session.rollback()
        return None
