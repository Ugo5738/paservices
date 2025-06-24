import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, status
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
) -> AppClientRoleResponse:
    """Assign a role to an app client. Admin only."""
    logger.info(
        f"Admin user attempting to assign role {role_assignment.role_id} to app client {client_id}"
    )

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

    logger.info(f"Successfully assigned role '{role.name}' to app client {client_id}")

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
) -> AppClientRoleListResponse:
    """List all roles assigned to an app client. Admin only."""
    logger.info(f"Admin user listing roles for app client {client_id}")

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
) -> MessageResponse:
    """Remove a role from an app client. Admin only."""
    logger.info(
        f"Admin user attempting to remove role {role_id} from app client {client_id}"
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

    logger.info(f"Successfully removed role '{role.name}' from app client {client_id}")

    return MessageResponse(message=f"Successfully removed role from app client")
