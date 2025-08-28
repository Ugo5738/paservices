import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth_service.db import get_db
from auth_service.dependencies.user_deps import require_admin_user
from auth_service.models.app_client import AppClient
from auth_service.models.app_client_role import AppClientRole
from auth_service.models.role import Role
from auth_service.schemas.app_client_role_schemas import (
    AppClientRoleAssign,
    AppClientRoleListResponse,
    AppClientRoleResponse,
)
from auth_service.schemas.common_schemas import MessageResponse
from auth_service.schemas.user_schemas import SupabaseUser

router = APIRouter(tags=["admin", "client-roles"])
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
    "client_secret_hash",
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
        return {"id": getattr(admin, "id", None), "email": getattr(admin, "email", None)}
    except Exception:
        return None


@router.post(
    "/{client_id}/roles",
    response_model=AppClientRoleResponse,
    status_code=status.HTTP_201_CREATED,
    description="Assign a role to an app client (admin only)",
)
async def assign_role_to_client(
    role_assignment: AppClientRoleAssign,
    client_id: uuid.UUID = Path(..., description="ID of the app client"),
    db: AsyncSession = Depends(get_db),
    current_admin: SupabaseUser = Depends(require_admin_user),
    http_request: Request | None = None,
) -> AppClientRoleResponse:
    """Assign a role to an app client. Admin only."""
    try:
        logger.info(
            "Inbound request: admin assign role to app client",
            extra={
                "request": {
                    "method": (http_request.method if http_request else None),
                    "path": (http_request.url.path if http_request else None),
                    "client_host": (
                        http_request.client.host if http_request and http_request.client else None
                    ),
                    "actor": _actor_from_admin(current_admin),
                },
                "params": {"client_id": str(client_id)},
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

    # Check if app client exists
    client_query = select(AppClient).where(AppClient.id == client_id)
    client_result = await db.execute(client_query)
    client = client_result.scalar_one_or_none()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App client with ID {client_id} not found",
        )

    # Check if role is already assigned to the app client
    client_role_query = select(AppClientRole).where(
        and_(
            AppClientRole.app_client_id == client_id,
            AppClientRole.role_id == role_assignment.role_id,
        )
    )
    client_role_result = await db.execute(client_role_query)
    existing_client_role = client_role_result.scalar_one_or_none()

    if existing_client_role:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role '{role.name}' is already assigned to app client {client_id}",
        )

    # Assign role to app client
    new_client_role = AppClientRole(
        app_client_id=client_id, role_id=role_assignment.role_id
    )
    db.add(new_client_role)
    await db.commit()
    await db.refresh(new_client_role)

    try:
        logger.info(
            "Outbound response: admin assign role to app client",
            extra={
                "status": 201,
                "client_id": str(client_id),
                "role": {"id": str(role.id), "name": role.name},
            },
        )
    except Exception:
        pass

    return AppClientRoleResponse(
        app_client_id=new_client_role.app_client_id,
        role_id=new_client_role.role_id,
        assigned_at=new_client_role.assigned_at,
    )


@router.get(
    "/{client_id}/roles",
    response_model=AppClientRoleListResponse,
    description="List all roles assigned to an app client (admin only)",
)
async def list_client_roles(
    client_id: uuid.UUID = Path(..., description="ID of the app client"),
    db: AsyncSession = Depends(get_db),
    current_admin: SupabaseUser = Depends(require_admin_user),
    http_request: Request | None = None,
) -> AppClientRoleListResponse:
    """List all roles assigned to an app client. Admin only."""
    try:
        logger.info(
            "Inbound request: admin list client roles",
            extra={
                "request": {
                    "method": (http_request.method if http_request else None),
                    "path": (http_request.url.path if http_request else None),
                    "client_host": (
                        http_request.client.host if http_request and http_request.client else None
                    ),
                    "actor": _actor_from_admin(current_admin),
                },
                "params": {"client_id": str(client_id)},
            },
        )
    except Exception:
        pass

    # Check if app client exists
    client_query = select(AppClient).where(AppClient.id == client_id)
    client_result = await db.execute(client_query)
    client = client_result.scalar_one_or_none()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App client with ID {client_id} not found",
        )

    # Query to get all roles assigned to the app client with role details
    query = (
        select(AppClientRole)
        .where(AppClientRole.app_client_id == client_id)
        .options(selectinload(AppClientRole.role))
    )
    result = await db.execute(query)
    client_roles = result.scalars().all()

    # Convert to response model
    client_role_responses = [
        AppClientRoleResponse(
            app_client_id=client_role.app_client_id,
            role_id=client_role.role_id,
            assigned_at=client_role.assigned_at,
        )
        for client_role in client_roles
    ]

    try:
        logger.info(
            "Outbound response: admin list client roles",
            extra={
                "status": 200,
                "client_id": str(client_id),
                "count": len(client_role_responses),
            },
        )
    except Exception:
        pass
    return AppClientRoleListResponse(
        items=client_role_responses, count=len(client_role_responses)
    )


@router.delete(
    "/{client_id}/roles/{role_id}",
    response_model=MessageResponse,
    description="Remove a role from an app client (admin only)",
)
async def remove_role_from_client(
    client_id: uuid.UUID = Path(..., description="ID of the app client"),
    role_id: uuid.UUID = Path(..., description="ID of the role to remove"),
    db: AsyncSession = Depends(get_db),
    current_admin: SupabaseUser = Depends(require_admin_user),
    http_request: Request | None = None,
) -> MessageResponse:
    """Remove a role from an app client. Admin only."""
    try:
        logger.info(
            "Inbound request: admin remove role from app client",
            extra={
                "request": {
                    "method": (http_request.method if http_request else None),
                    "path": (http_request.url.path if http_request else None),
                    "client_host": (
                        http_request.client.host if http_request and http_request.client else None
                    ),
                    "actor": _actor_from_admin(current_admin),
                },
                "params": {"client_id": str(client_id), "role_id": str(role_id)},
            },
        )
    except Exception:
        pass

    # Check if app client exists
    client_query = select(AppClient).where(AppClient.id == client_id)
    client_result = await db.execute(client_query)
    client = client_result.scalar_one_or_none()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App client with ID {client_id} not found",
        )

    # Check if the role is assigned to the app client
    query = (
        select(AppClientRole)
        .join(Role)
        .where(
            and_(
                AppClientRole.app_client_id == client_id,
                AppClientRole.role_id == role_id,
            )
        )
    )
    result = await db.execute(query)
    client_role = result.scalar_one_or_none()

    if not client_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} is not assigned to app client {client_id}",
        )

    # Get role name for logging
    role_query = select(Role).where(Role.id == role_id)
    role_result = await db.execute(role_query)
    role = role_result.scalar_one()

    # Remove the role from the app client
    await db.delete(client_role)
    await db.commit()

    try:
        logger.info(
            "Outbound response: admin remove role from app client",
            extra={
                "status": 200,
                "client_id": str(client_id),
                "role": {"id": str(role.id), "name": role.name},
            },
        )
    except Exception:
        pass

    return MessageResponse(message=f"Successfully removed role from app client")
