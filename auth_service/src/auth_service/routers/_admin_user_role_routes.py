import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth_service.db import get_db
from auth_service.dependencies.user_deps import require_admin_user
from auth_service.models.role import Role
from auth_service.models.user_role import UserRole
from auth_service.schemas.common_schemas import MessageResponse
from auth_service.schemas.user_role_schemas import (
    UserRoleAssign,
    UserRoleListResponse,
    UserRoleResponse,
)
from auth_service.schemas.user_schemas import SupabaseUser

router = APIRouter(tags=["admin", "user-roles"])
logger = logging.getLogger(__name__)


# Local helpers for safe structured logging
SENSITIVE_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "secret",
    "client_secret",
    "api_key",
    "code",
}


def _redact_sensitive(data: dict | None) -> dict | None:
    if not isinstance(data, dict):
        return None
    redacted: dict = {}
    for k, v in data.items():
        if k and str(k).lower() in SENSITIVE_KEYS:
            redacted[k] = "[REDACTED]"
        else:
            redacted[k] = v
    return redacted


def _actor_from_admin(admin: SupabaseUser | None) -> dict | None:
    if not admin:
        return None
    try:
        return {
            "id": getattr(admin, "id", None),
            "email": getattr(admin, "email", None),
        }
    except Exception:
        return None


@router.post(
    "/{user_id}/roles",
    response_model=UserRoleResponse,
    status_code=status.HTTP_201_CREATED,
    description="Assign a role to a user (admin only)",
)
async def assign_role_to_user(
    role_assignment: UserRoleAssign,
    user_id: uuid.UUID = Path(..., description="ID of the user"),
    db: AsyncSession = Depends(get_db),
    current_admin: SupabaseUser = Depends(require_admin_user),
    http_request: Request | None = None,
) -> UserRoleResponse:
    """Assign a role to a user. Admin only."""
    try:
        logger.info(
            "Inbound request: admin assign role to user",
            extra={
                "request": {
                    "method": (http_request.method if http_request else None),
                    "path": (http_request.url.path if http_request else None),
                    "client_host": (
                        http_request.client.host
                        if http_request and http_request.client
                        else None
                    ),
                    "actor": _actor_from_admin(current_admin),
                },
                "params": {"user_id": str(user_id)},
                "body_excerpt": _redact_sensitive(role_assignment.model_dump()),
            },
        )
    except Exception:
        pass

    # Check if role exists
    role_query = select(Role).where(Role.id == role_assignment.role_id)
    role_result = await db.execute(role_query)
    role = role_result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_assignment.role_id} not found",
        )

    # In a real scenario, we would check if the user exists in Supabase
    # For this implementation, we'll assume the user_id is valid if it's a valid UUID

    # Check if role is already assigned to the user
    user_role_query = select(UserRole).where(
        and_(UserRole.user_id == user_id, UserRole.role_id == role_assignment.role_id)
    )
    user_role_result = await db.execute(user_role_query)
    existing_user_role = user_role_result.scalar_one_or_none()

    if existing_user_role:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role '{role.name}' is already assigned to user {user_id}",
        )

    # Assign role to user
    new_user_role = UserRole(user_id=user_id, role_id=role_assignment.role_id)
    db.add(new_user_role)
    await db.commit()
    await db.refresh(new_user_role)

    try:
        logger.info(
            "Outbound response: admin assign role to user",
            extra={
                "status": 201,
                "user_id": str(user_id),
                "role_id": str(new_user_role.role_id),
            },
        )
    except Exception:
        pass

    return UserRoleResponse(
        user_id=new_user_role.user_id,
        role_id=new_user_role.role_id,
        assigned_at=new_user_role.assigned_at,
    )


@router.get(
    "/{user_id}/roles",
    response_model=UserRoleListResponse,
    description="List all roles assigned to a user (admin only)",
)
async def list_user_roles(
    user_id: uuid.UUID = Path(..., description="ID of the user"),
    db: AsyncSession = Depends(get_db),
    current_admin: SupabaseUser = Depends(require_admin_user),
    http_request: Request | None = None,
) -> UserRoleListResponse:
    """List all roles assigned to a user. Admin only."""
    try:
        logger.info(
            "Inbound request: admin list user roles",
            extra={
                "request": {
                    "method": (http_request.method if http_request else None),
                    "path": (http_request.url.path if http_request else None),
                    "client_host": (
                        http_request.client.host
                        if http_request and http_request.client
                        else None
                    ),
                    "actor": _actor_from_admin(current_admin),
                },
                "params": {"user_id": str(user_id)},
            },
        )
    except Exception:
        pass

    # Query to get all roles assigned to the user with role details
    query = (
        select(UserRole)
        .where(UserRole.user_id == user_id)
        .options(selectinload(UserRole.role))
    )
    result = await db.execute(query)
    user_roles = result.scalars().all()

    # Convert to response model
    user_role_responses = [
        UserRoleResponse(
            user_id=user_role.user_id,
            role_id=user_role.role_id,
            assigned_at=user_role.assigned_at,
        )
        for user_role in user_roles
    ]

    try:
        logger.info(
            "Outbound response: admin list user roles",
            extra={
                "status": 200,
                "user_id": str(user_id),
                "count": len(user_role_responses),
            },
        )
    except Exception:
        pass
    return UserRoleListResponse(
        items=user_role_responses, count=len(user_role_responses)
    )


@router.delete(
    "/{user_id}/roles/{role_id}",
    response_model=MessageResponse,
    description="Remove a role from a user (admin only)",
)
async def remove_role_from_user(
    user_id: uuid.UUID = Path(..., description="ID of the user"),
    role_id: uuid.UUID = Path(..., description="ID of the role to remove"),
    db: AsyncSession = Depends(get_db),
    current_admin: SupabaseUser = Depends(require_admin_user),
    http_request: Request | None = None,
) -> MessageResponse:
    """Remove a role from a user. Admin only."""
    try:
        logger.info(
            "Inbound request: admin remove role from user",
            extra={
                "request": {
                    "method": (http_request.method if http_request else None),
                    "path": (http_request.url.path if http_request else None),
                    "client_host": (
                        http_request.client.host
                        if http_request and http_request.client
                        else None
                    ),
                    "actor": _actor_from_admin(current_admin),
                },
                "params": {"user_id": str(user_id), "role_id": str(role_id)},
            },
        )
    except Exception:
        pass

    # Check if the role is assigned to the user
    query = (
        select(UserRole)
        .join(Role)
        .where(and_(UserRole.user_id == user_id, UserRole.role_id == role_id))
    )
    result = await db.execute(query)
    user_role = result.scalar_one_or_none()

    if not user_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} is not assigned to user {user_id}",
        )

    # Get role name for logging
    role_query = select(Role).where(Role.id == role_id)
    role_result = await db.execute(role_query)
    role = role_result.scalar_one()

    # Remove the role from the user
    await db.delete(user_role)
    await db.commit()

    try:
        logger.info(
            "Outbound response: admin remove role from user",
            extra={
                "status": 200,
                "user_id": str(user_id),
                "role_id": str(role_id),
            },
        )
    except Exception:
        pass

    return MessageResponse(message=f"Successfully removed role from user")
