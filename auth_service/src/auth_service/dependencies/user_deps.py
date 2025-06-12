import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from gotrue.errors import AuthApiError as SupabaseAPIError
from supabase._async.client import AsyncClient as AsyncSupabaseClient

from auth_service.schemas.user_schemas import SupabaseUser
from auth_service.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/users/login")


async def get_current_supabase_user(
    token: str = Depends(oauth2_scheme),
    supabase: AsyncSupabaseClient = Depends(get_supabase_client),
) -> SupabaseUser:
    """
    Dependency to get the current authenticated Supabase user from a JWT.
    Validates the token and returns the user object or raises HTTPException.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        logger.debug(
            f"Attempting to get user with token: {token[:20]}..."
        )  # Log truncated token
        user_response = await supabase.auth.get_user(jwt=token)

        if not user_response or not user_response.user:
            logger.warning(
                f"Token validation failed or no user returned for token: {token[:20]}..."
            )
            raise credentials_exception

        current_user = SupabaseUser(
            id=user_response.user.id,
            aud=user_response.user.aud or "",
            role=user_response.user.role,
            email=user_response.user.email,
            phone=user_response.user.phone,
            email_confirmed_at=user_response.user.email_confirmed_at,
            phone_confirmed_at=user_response.user.phone_confirmed_at,
            confirmed_at=getattr(
                user_response.user,
                "confirmed_at",
                user_response.user.email_confirmed_at
                or user_response.user.phone_confirmed_at,
            ),
            last_sign_in_at=user_response.user.last_sign_in_at,
            app_metadata=user_response.user.app_metadata or {},
            user_metadata=user_response.user.user_metadata or {},
            identities=user_response.user.identities or [],
            created_at=user_response.user.created_at,
            updated_at=user_response.user.updated_at,
        )
        logger.info(f"Successfully validated token for user: {current_user.email}")
        return current_user
    except SupabaseAPIError as e:
        logger.warning(
            f"Supabase API error during token validation: {e.message} (Status: {e.status})"
        )
        if e.message == "Token expired" or e.status == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or expired token: {e.message}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        raise credentials_exception
    except Exception as e:
        logger.error(f"Unexpected error during token validation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while validating authentication token.",
        )


async def require_admin_user(
    current_user: SupabaseUser = Depends(get_current_supabase_user),
) -> SupabaseUser:
    """
    Dependency to ensure the current user has admin privileges.
    Checks for:
    1. Legacy 'admin' role in user_metadata
    2. RBAC system: 'admin' role in user JWT claims
    3. RBAC system: 'role:admin_manage' permission in user JWT claims

    Raises HTTPException 403 if the user does not have admin privileges.
    Returns the user object if they have admin privileges.
    """
    # Check legacy admin role in user_metadata
    user_metadata_roles = current_user.user_metadata.get("roles", [])

    # Check RBAC roles and permissions in JWT claims
    user_jwt_roles = current_user.app_metadata.get("roles", [])
    user_jwt_permissions = current_user.app_metadata.get("permissions", [])

    # Check if user has admin privileges via any method
    has_admin_role = "admin" in user_metadata_roles or "admin" in user_jwt_roles
    has_admin_permission = "role:admin_manage" in user_jwt_permissions

    if not (has_admin_role or has_admin_permission):
        logger.warning(
            f"Admin access denied for user {current_user.email}. "
            f"Metadata roles: {user_metadata_roles}, "
            f"JWT roles: {user_jwt_roles}, "
            f"JWT permissions: {user_jwt_permissions}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have admin privileges",
        )

    logger.info(
        f"Admin access granted for user: {current_user.email}. "
        f"Admin role: {has_admin_role}, Admin permission: {has_admin_permission}"
    )
    return current_user
