import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.db import get_db
from auth_service.dependencies.user_deps import require_admin_user
from auth_service.models.permission import Permission
from auth_service.schemas.common_schemas import MessageResponse
from auth_service.schemas.permission_schemas import (
    PermissionCreate,
    PermissionListResponse,
    PermissionResponse,
    PermissionUpdate,
)
from auth_service.schemas.user_schemas import SupabaseUser

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["admin", "permissions"],
)


def _redact_sensitive(data):
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
    if isinstance(data, dict):
        return {
            k: ("<redacted>" if k.lower() in SENSITIVE_KEYS else _redact_sensitive(v))
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_redact_sensitive(v) for v in data]
    return data


def _actor_from_admin(user: SupabaseUser) -> dict:
    try:
        return {"user_id": getattr(user, "id", None)}
    except Exception:
        return {"user_id": None}

@router.post(
    "",
    response_model=PermissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new permission",
    responses={
        status.HTTP_201_CREATED: {"model": PermissionResponse},
        status.HTTP_400_BAD_REQUEST: {"model": MessageResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": MessageResponse},
        status.HTTP_403_FORBIDDEN: {"model": MessageResponse},
        status.HTTP_409_CONFLICT: {"model": MessageResponse},
    },
)
async def create_permission(
    permission_data: PermissionCreate,
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
    http_request: Request = None,
) -> PermissionResponse:
    """
    Create a new permission. This endpoint is restricted to admin users.

    - **name**: Unique name for the permission (e.g., 'users:read')
    - **description**: Optional description of the permission
    """
    # Inbound log (no sensitive fields)
    try:
        logger.info(
            "Inbound request: admin create permission",
            extra={
                "request": {
                    "method": http_request.method if http_request else None,
                    "path": http_request.url.path if http_request else None,
                    "client_host": (http_request.client.host if http_request and http_request.client else None),
                    "actor": _actor_from_admin(_current_admin),
                },
                "body_excerpt": _redact_sensitive(permission_data.model_dump()),
            },
        )
    except Exception:
        pass

    # Check if permission with the same name already exists
    query = select(Permission).where(Permission.name == permission_data.name)
    result = await db.execute(query)
    existing_permission = result.scalar_one_or_none()

    if existing_permission:
        logger.warning(f"Permission with name '{permission_data.name}' already exists")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Permission with name '{permission_data.name}' already exists",
        )

    # Create new permission
    try:
        new_permission = Permission(
            name=permission_data.name, description=permission_data.description
        )
        db.add(new_permission)
        await db.commit()
        await db.refresh(new_permission)

        logger.info(
            "Outbound response: admin create permission",
            extra={"permission_id": str(new_permission.id), "name": new_permission.name},
        )
        return new_permission
    except IntegrityError as e:
        await db.rollback()
        logger.error(f"Database integrity error creating permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Permission could not be created due to a database constraint",
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the permission",
        )


@router.get(
    "",
    response_model=PermissionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all permissions",
    responses={
        status.HTTP_200_OK: {"model": PermissionListResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": MessageResponse},
        status.HTTP_403_FORBIDDEN: {"model": MessageResponse},
    },
)
async def list_permissions(
    skip: int = Query(0, ge=0, description="Number of permissions to skip"),
    limit: int = Query(
        100, ge=1, le=100, description="Maximum number of permissions to return"
    ),
    search: Optional[str] = Query(
        None, description="Optional search term for permission name"
    ),
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
    http_request: Request = None,
) -> PermissionListResponse:
    """
    List all permissions with pagination and optional search. This endpoint is restricted to admin users.

    - **skip**: Number of permissions to skip (pagination)
    - **limit**: Maximum number of permissions to return (pagination)
    - **search**: Optional search term for permission name
    """
    try:
        logger.info(
            "Inbound request: admin list permissions",
            extra={
                "request": {
                    "method": http_request.method if http_request else None,
                    "path": http_request.url.path if http_request else None,
                    "client_host": (http_request.client.host if http_request and http_request.client else None),
                    "actor": _actor_from_admin(_current_admin),
                },
                "query": {"skip": skip, "limit": limit, "search": search},
            },
        )
    except Exception:
        pass

    # Build base query
    query = select(Permission)
    count_query = select(func.count()).select_from(Permission)

    # Apply search filter if provided
    if search:
        query = query.where(Permission.name.ilike(f"%{search}%"))
        count_query = count_query.where(Permission.name.ilike(f"%{search}%"))

    # Apply pagination
    query = query.offset(skip).limit(limit)

    # Execute queries
    result = await db.execute(query)
    count_result = await db.execute(count_query)

    permissions = result.scalars().all()
    total_count = count_result.scalar_one()

    logger.info(
        "Outbound response: admin list permissions",
        extra={"count": len(permissions), "total": total_count},
    )

    return PermissionListResponse(items=permissions, count=total_count)


@router.get(
    "/{permission_id}",
    response_model=PermissionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a specific permission by ID",
    responses={
        status.HTTP_200_OK: {"model": PermissionResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": MessageResponse},
        status.HTTP_403_FORBIDDEN: {"model": MessageResponse},
        status.HTTP_404_NOT_FOUND: {"model": MessageResponse},
    },
)
async def get_permission(
    permission_id: uuid.UUID = Path(
        ..., description="The ID of the permission to retrieve"
    ),
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
    http_request: Request = None,
) -> PermissionResponse:
    """
    Get a specific permission by ID. This endpoint is restricted to admin users.

    - **permission_id**: The unique identifier of the permission to retrieve
    """
    try:
        logger.info(
            "Inbound request: admin get permission",
            extra={
                "request": {
                    "method": http_request.method if http_request else None,
                    "path": http_request.url.path if http_request else None,
                    "client_host": (http_request.client.host if http_request and http_request.client else None),
                    "actor": _actor_from_admin(_current_admin),
                },
                "permission_id": str(permission_id),
            },
        )
    except Exception:
        pass

    # Get the permission by ID
    permission = await db.get(Permission, permission_id)
    if not permission:
        logger.warning(f"Permission with ID '{permission_id}' not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission with ID '{permission_id}' not found",
        )

    return permission


@router.put(
    "/{permission_id}",
    response_model=PermissionResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a permission",
    responses={
        status.HTTP_200_OK: {"model": PermissionResponse},
        status.HTTP_400_BAD_REQUEST: {"model": MessageResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": MessageResponse},
        status.HTTP_403_FORBIDDEN: {"model": MessageResponse},
        status.HTTP_404_NOT_FOUND: {"model": MessageResponse},
        status.HTTP_409_CONFLICT: {"model": MessageResponse},
    },
)
async def update_permission(
    permission_data: PermissionUpdate,
    permission_id: uuid.UUID = Path(
        ..., description="The ID of the permission to update"
    ),
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
    http_request: Request = None,
) -> PermissionResponse:
    """
    Update a permission. This endpoint is restricted to admin users.

    - **permission_id**: The unique identifier of the permission to update
    - **name**: New name for the permission (optional)
    - **description**: New description for the permission (optional)
    """
    try:
        logger.info(
            "Inbound request: admin update permission",
            extra={
                "request": {
                    "method": http_request.method if http_request else None,
                    "path": http_request.url.path if http_request else None,
                    "client_host": (http_request.client.host if http_request and http_request.client else None),
                    "actor": _actor_from_admin(_current_admin),
                },
                "permission_id": str(permission_id),
                "body_excerpt": _redact_sensitive(permission_data.model_dump()),
            },
        )
    except Exception:
        pass

    # Validate that at least one field is provided for update
    if not permission_data.name and permission_data.description is None:
        logger.warning("No update fields provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided for update",
        )

    # Get the permission by ID
    permission = await db.get(Permission, permission_id)
    if not permission:
        logger.warning(f"Permission with ID '{permission_id}' not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission with ID '{permission_id}' not found",
        )

    # Check if the new name already exists (if name is being updated)
    if permission_data.name and permission_data.name != permission.name:
        query = select(Permission).where(Permission.name == permission_data.name)
        result = await db.execute(query)
        existing_permission = result.scalar_one_or_none()

        if existing_permission:
            logger.warning(
                f"Permission with name '{permission_data.name}' already exists"
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Permission with name '{permission_data.name}' already exists",
            )

    # Update permission fields
    try:
        if permission_data.name:
            permission.name = permission_data.name
        if (
            permission_data.description is not None
        ):  # Allow empty string to clear description
            permission.description = permission_data.description

        await db.commit()
        await db.refresh(permission)

        logger.info(
            "Outbound response: admin update permission",
            extra={"permission_id": str(permission_id)},
        )
        return permission
    except IntegrityError as e:
        await db.rollback()
        logger.error(f"Database integrity error updating permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Permission could not be updated due to a database constraint",
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the permission",
        )


@router.delete(
    "/{permission_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a permission",
    responses={
        status.HTTP_200_OK: {"model": MessageResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": MessageResponse},
        status.HTTP_403_FORBIDDEN: {"model": MessageResponse},
        status.HTTP_404_NOT_FOUND: {"model": MessageResponse},
    },
)
async def delete_permission(
    permission_id: uuid.UUID = Path(
        ..., description="The ID of the permission to delete"
    ),
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
    http_request: Request = None,
) -> MessageResponse:
    """
    Delete a permission. This endpoint is restricted to admin users.

    - **permission_id**: The unique identifier of the permission to delete
    """
    try:
        logger.info(
            "Inbound request: admin delete permission",
            extra={
                "request": {
                    "method": http_request.method if http_request else None,
                    "path": http_request.url.path if http_request else None,
                    "client_host": (http_request.client.host if http_request and http_request.client else None),
                    "actor": _actor_from_admin(_current_admin),
                },
                "permission_id": str(permission_id),
            },
        )
    except Exception:
        pass

    # Get the permission by ID
    permission = await db.get(Permission, permission_id)
    if not permission:
        logger.warning(f"Permission with ID '{permission_id}' not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission with ID '{permission_id}' not found",
        )

    permission_name = permission.name  # Store for logging

    try:
        # Delete the permission
        await db.delete(permission)
        await db.commit()
        logger.info(
            "Outbound response: admin delete permission",
            extra={"permission_id": str(permission_id), "name": permission_name},
        )
    except Exception as e:
        await db.rollback()
        logger.error(
            f"Error deleting permission '{permission_name}' with ID {permission_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the permission",
        )

    return MessageResponse(
        message=f"Permission '{permission_name}' successfully deleted"
    )
