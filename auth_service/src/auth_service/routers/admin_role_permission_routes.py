import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.db import get_db
from auth_service.dependencies.user_deps import require_admin_user
from auth_service.models.role import Role
from auth_service.models.permission import Permission
from auth_service.models.role_permission import RolePermission
from auth_service.schemas.common_schemas import MessageResponse
from auth_service.schemas.role_permission_schemas import (
    RolePermissionAssign,
    RolePermissionResponse,
    RolePermissionListResponse
)
from auth_service.schemas.user_schemas import SupabaseUser

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/roles/{role_id}/permissions",
    tags=["admin", "roles", "permissions"],
)


@router.post(
    "",
    response_model=RolePermissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a permission to a role",
    responses={
        status.HTTP_201_CREATED: {"model": RolePermissionResponse},
        status.HTTP_400_BAD_REQUEST: {"model": MessageResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": MessageResponse},
        status.HTTP_403_FORBIDDEN: {"model": MessageResponse},
        status.HTTP_404_NOT_FOUND: {"model": MessageResponse},
        status.HTTP_409_CONFLICT: {"model": MessageResponse},
    },
)
async def assign_permission_to_role(
    role_assignment: RolePermissionAssign,
    role_id: uuid.UUID = Path(..., description="The ID of the role to assign the permission to"),
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
) -> RolePermissionResponse:
    """
    Assign a permission to a role. This endpoint is restricted to admin users.
    
    - **role_id**: The unique identifier of the role
    - **permission_id**: The unique identifier of the permission to assign
    """
    logger.info(f"Admin user attempting to assign permission {role_assignment.permission_id} to role {role_id}")
    
    # Verify the role exists
    role = await db.get(Role, role_id)
    if not role:
        logger.warning(f"Role with ID '{role_id}' not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID '{role_id}' not found"
        )
    
    # Verify the permission exists
    permission = await db.get(Permission, role_assignment.permission_id)
    if not permission:
        logger.warning(f"Permission with ID '{role_assignment.permission_id}' not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission with ID '{role_assignment.permission_id}' not found"
        )
    
    # Check if the permission is already assigned to the role
    query = select(RolePermission).where(
        RolePermission.role_id == role_id,
        RolePermission.permission_id == role_assignment.permission_id
    )
    result = await db.execute(query)
    existing_assignment = result.scalar_one_or_none()
    
    if existing_assignment:
        logger.warning(f"Permission '{permission.name}' is already assigned to role '{role.name}'")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Permission '{permission.name}' is already assigned to role '{role.name}'"
        )
    
    # Create the role-permission assignment
    try:
        role_permission = RolePermission(
            role_id=role_id,
            permission_id=role_assignment.permission_id
        )
        db.add(role_permission)
        await db.commit()
        await db.refresh(role_permission)
        
        logger.info(f"Successfully assigned permission '{permission.name}' to role '{role.name}'")
        return role_permission
    except IntegrityError as e:
        await db.rollback()
        logger.error(f"Database integrity error assigning permission to role: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Permission could not be assigned to role due to a database constraint"
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error assigning permission to role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while assigning the permission to the role"
        )


@router.get(
    "",
    response_model=RolePermissionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all permissions assigned to a role",
    responses={
        status.HTTP_200_OK: {"model": RolePermissionListResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": MessageResponse},
        status.HTTP_403_FORBIDDEN: {"model": MessageResponse},
        status.HTTP_404_NOT_FOUND: {"model": MessageResponse},
    },
)
async def list_role_permissions(
    role_id: uuid.UUID = Path(..., description="The ID of the role to list permissions for"),
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
) -> RolePermissionListResponse:
    """
    List all permissions assigned to a role. This endpoint is restricted to admin users.
    
    - **role_id**: The unique identifier of the role to list permissions for
    """
    logger.info(f"Admin user retrieving permissions for role with ID: {role_id}")
    
    # Verify the role exists
    role = await db.get(Role, role_id)
    if not role:
        logger.warning(f"Role with ID '{role_id}' not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID '{role_id}' not found"
        )
    
    # Query for role-permission assignments
    query = select(RolePermission).where(RolePermission.role_id == role_id)
    count_query = select(func.count()).select_from(RolePermission).where(RolePermission.role_id == role_id)
    
    # Execute queries
    result = await db.execute(query)
    count_result = await db.execute(count_query)
    
    role_permissions = result.scalars().all()
    total_count = count_result.scalar_one()
    
    logger.info(f"Retrieved {len(role_permissions)} permissions for role '{role.name}'")
    
    return RolePermissionListResponse(
        items=role_permissions,
        count=total_count
    )


@router.delete(
    "/{permission_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove a permission from a role",
    responses={
        status.HTTP_200_OK: {"model": MessageResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": MessageResponse},
        status.HTTP_403_FORBIDDEN: {"model": MessageResponse},
        status.HTTP_404_NOT_FOUND: {"model": MessageResponse},
    },
)
async def remove_permission_from_role(
    role_id: uuid.UUID = Path(..., description="The ID of the role to remove the permission from"),
    permission_id: uuid.UUID = Path(..., description="The ID of the permission to remove"),
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
) -> MessageResponse:
    """
    Remove a permission from a role. This endpoint is restricted to admin users.
    
    - **role_id**: The unique identifier of the role
    - **permission_id**: The unique identifier of the permission to remove
    """
    logger.info(f"Admin user attempting to remove permission {permission_id} from role {role_id}")
    
    # Verify the role exists
    role = await db.get(Role, role_id)
    if not role:
        logger.warning(f"Role with ID '{role_id}' not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID '{role_id}' not found"
        )
    
    # Verify the permission exists
    permission = await db.get(Permission, permission_id)
    if not permission:
        logger.warning(f"Permission with ID '{permission_id}' not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission with ID '{permission_id}' not found"
        )
    
    # Find the role-permission assignment
    query = select(RolePermission).where(
        RolePermission.role_id == role_id,
        RolePermission.permission_id == permission_id
    )
    result = await db.execute(query)
    assignment = result.scalar_one_or_none()
    
    if not assignment:
        logger.warning(f"Permission '{permission.name}' is not assigned to role '{role.name}'")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission '{permission.name}' is not assigned to role '{role.name}'"
        )
    
    # Remove the role-permission assignment
    try:
        await db.delete(assignment)
        await db.commit()
        logger.info(f"Successfully removed permission '{permission.name}' from role '{role.name}'")
        return MessageResponse(message=f"Permission '{permission.name}' successfully removed from role '{role.name}'")
    except Exception as e:
        await db.rollback()
        logger.error(f"Error removing permission from role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while removing the permission from the role"
        )
