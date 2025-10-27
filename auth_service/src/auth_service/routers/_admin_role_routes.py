import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..dependencies.user_deps import require_admin_user
from ..models.role import Role
from ..schemas.common_schemas import MessageResponse
from ..schemas.role_schemas import (
    RoleCreate,
    RoleListResponse,
    RoleResponse,
    RoleUpdate,
)
from ..schemas.user_schemas import SupabaseUser

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["admin", "roles"],
)


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
    "",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new role",
    responses={
        status.HTTP_201_CREATED: {"model": RoleResponse},
        status.HTTP_400_BAD_REQUEST: {"model": MessageResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": MessageResponse},
        status.HTTP_403_FORBIDDEN: {"model": MessageResponse},
        status.HTTP_409_CONFLICT: {"model": MessageResponse},
    },
)
async def create_role(
    request: Request,
    role_data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
) -> RoleResponse:
    """
    Create a new role. This endpoint is restricted to admin users.

    - **name**: Unique name for the role
    - **description**: Optional description of the role
    """
    try:
        logger.info(
            "Inbound request: admin create role",
            extra={
                "request": {
                    "method": (request.method if request else None),
                    "path": (request.url.path if request else None),
                    "client_host": (
                        request.client.host if request and request.client else None
                    ),
                    "actor": _actor_from_admin(_current_admin),
                },
                "body_excerpt": _redact_sensitive(role_data.model_dump()),
            },
        )
    except Exception:
        pass

    # Check if role with the same name already exists
    query = select(Role).where(Role.name == role_data.name)
    result = await db.execute(query)
    existing_role = result.scalar_one_or_none()

    if existing_role:
        logger.warning(f"Role with name '{role_data.name}' already exists")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role with name '{role_data.name}' already exists",
        )

    # Create new role
    try:
        new_role = Role(name=role_data.name, description=role_data.description)
        db.add(new_role)
        await db.commit()
        await db.refresh(new_role)

        try:
            logger.info(
                "Outbound response: admin create role",
                extra={
                    "status": 201,
                    "role": {"id": str(new_role.id), "name": new_role.name},
                },
            )
        except Exception:
            pass
        return new_role
    except IntegrityError as e:
        await db.rollback()
        logger.error(f"Database integrity error creating role: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role could not be created due to a database constraint",
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the role",
        )


@router.get(
    "",
    response_model=RoleListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all roles",
    responses={
        status.HTTP_200_OK: {"model": RoleListResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": MessageResponse},
        status.HTTP_403_FORBIDDEN: {"model": MessageResponse},
    },
)
async def list_roles(
    request: Request,
    skip: int = Query(0, ge=0, description="Number of roles to skip"),
    limit: int = Query(
        100, ge=1, le=100, description="Maximum number of roles to return"
    ),
    search: Optional[str] = Query(
        None, description="Optional search term for role name"
    ),
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
) -> RoleListResponse:
    """
    List all roles with pagination and optional search. This endpoint is restricted to admin users.

    - **skip**: Number of roles to skip (pagination)
    - **limit**: Maximum number of roles to return (pagination)
    - **search**: Optional search term for role name
    """
    try:
        logger.info(
            "Inbound request: admin list roles",
            extra={
                "request": {
                    "method": (request.method if request else None),
                    "path": (request.url.path if request else None),
                    "client_host": (
                        request.client.host if request and request.client else None
                    ),
                    "actor": _actor_from_admin(_current_admin),
                },
                "query": {"skip": skip, "limit": limit, "search": search},
            },
        )
    except Exception:
        pass

    # Build base query
    query = select(Role)
    count_query = select(func.count()).select_from(Role)

    # Apply search filter if provided
    if search:
        query = query.where(Role.name.ilike(f"%{search}%"))
        count_query = count_query.where(Role.name.ilike(f"%{search}%"))

    # Apply pagination
    query = query.offset(skip).limit(limit)

    # Execute queries
    result = await db.execute(query)
    count_result = await db.execute(count_query)

    roles = result.scalars().all()
    total_count = count_result.scalar_one()

    try:
        logger.info(
            "Outbound response: admin list roles",
            extra={
                "status": 200,
                "count": len(roles),
                "total": total_count,
            },
        )
    except Exception:
        pass

    return RoleListResponse(items=roles, count=total_count)


@router.get(
    "/{role_id}",
    response_model=RoleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a specific role by ID",
    responses={
        status.HTTP_200_OK: {"model": RoleResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": MessageResponse},
        status.HTTP_403_FORBIDDEN: {"model": MessageResponse},
        status.HTTP_404_NOT_FOUND: {"model": MessageResponse},
    },
)
async def get_role(
    request: Request,
    role_id: uuid.UUID = Path(..., description="The ID of the role to retrieve"),
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
) -> RoleResponse:
    """
    Get a specific role by ID. This endpoint is restricted to admin users.

    - **role_id**: The unique identifier of the role to retrieve
    """
    try:
        logger.info(
            "Inbound request: admin get role",
            extra={
                "request": {
                    "method": (request.method if request else None),
                    "path": (request.url.path if request else None),
                    "client_host": (
                        request.client.host if request and request.client else None
                    ),
                    "actor": _actor_from_admin(_current_admin),
                },
                "params": {"role_id": str(role_id)},
            },
        )
    except Exception:
        pass

    # Get the role by ID
    role = await db.get(Role, role_id)
    if not role:
        logger.warning(f"Role with ID '{role_id}' not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID '{role_id}' not found",
        )

    return role


@router.put(
    "/{role_id}",
    response_model=RoleResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a role",
    responses={
        status.HTTP_200_OK: {"model": RoleResponse},
        status.HTTP_400_BAD_REQUEST: {"model": MessageResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": MessageResponse},
        status.HTTP_403_FORBIDDEN: {"model": MessageResponse},
        status.HTTP_404_NOT_FOUND: {"model": MessageResponse},
        status.HTTP_409_CONFLICT: {"model": MessageResponse},
    },
)
async def update_role(
    request: Request,
    role_data: RoleUpdate,
    role_id: uuid.UUID = Path(..., description="The ID of the role to update"),
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
) -> RoleResponse:
    """
    Update a role. This endpoint is restricted to admin users.

    - **role_id**: The unique identifier of the role to update
    - **name**: New name for the role (optional)
    - **description**: New description for the role (optional)
    """
    try:
        logger.info(
            "Inbound request: admin update role",
            extra={
                "request": {
                    "method": (request.method if request else None),
                    "path": (request.url.path if request else None),
                    "client_host": (
                        request.client.host if request and request.client else None
                    ),
                    "actor": _actor_from_admin(_current_admin),
                },
                "params": {"role_id": str(role_id)},
                "body_excerpt": _redact_sensitive(
                    role_data.model_dump(exclude_unset=True)
                ),
            },
        )
    except Exception:
        pass

    # Validate that at least one field is provided for update
    if not role_data.name and role_data.description is None:
        logger.warning("No update fields provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided for update",
        )

    # Get the role by ID
    role = await db.get(Role, role_id)
    if not role:
        logger.warning(f"Role with ID '{role_id}' not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID '{role_id}' not found",
        )

    # Check if the new name already exists (if name is being updated)
    if role_data.name and role_data.name != role.name:
        query = select(Role).where(Role.name == role_data.name)
        result = await db.execute(query)
        existing_role = result.scalar_one_or_none()

        if existing_role:
            logger.warning(f"Role with name '{role_data.name}' already exists")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Role with name '{role_data.name}' already exists",
            )

    # Update role fields
    try:
        if role_data.name:
            role.name = role_data.name
        if role_data.description is not None:  # Allow empty string to clear description
            role.description = role_data.description

        await db.commit()
        await db.refresh(role)

        try:
            logger.info(
                "Outbound response: admin update role",
                extra={"status": 200, "role": {"id": str(role.id), "name": role.name}},
            )
        except Exception:
            pass
        return role
    except IntegrityError as e:
        await db.rollback()
        logger.error(f"Database integrity error updating role: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role could not be updated due to a database constraint",
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the role",
        )


@router.delete(
    "/{role_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a role",
    responses={
        status.HTTP_200_OK: {"model": MessageResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": MessageResponse},
        status.HTTP_403_FORBIDDEN: {"model": MessageResponse},
        status.HTTP_404_NOT_FOUND: {"model": MessageResponse},
    },
)
async def delete_role(
    request: Request,
    role_id: uuid.UUID = Path(..., description="The ID of the role to delete"),
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
) -> MessageResponse:
    """
    Delete a role. This endpoint is restricted to admin users.

    - **role_id**: The unique identifier of the role to delete
    """
    try:
        logger.info(
            "Inbound request: admin delete role",
            extra={
                "request": {
                    "method": (request.method if request else None),
                    "path": (request.url.path if request else None),
                    "client_host": (
                        request.client.host if request and request.client else None
                    ),
                    "actor": _actor_from_admin(_current_admin),
                },
                "params": {"role_id": str(role_id)},
            },
        )
    except Exception:
        pass

    # Get the role by ID
    role = await db.get(Role, role_id)
    if not role:
        logger.warning(f"Role with ID '{role_id}' not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID '{role_id}' not found",
        )

    role_name = role.name  # Store for logging

    try:
        # Delete the role
        await db.delete(role)
        await db.commit()
        try:
            logger.info(
                "Outbound response: admin delete role",
                extra={
                    "status": 200,
                    "role": {"id": str(role_id), "name": role_name},
                },
            )
        except Exception:
            pass
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting role '{role_name}' with ID {role_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the role",
        )

    return MessageResponse(message=f"Role '{role_name}' successfully deleted")
