import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.db import get_db
from auth_service.dependencies.user_deps import require_admin_user
from auth_service.models.role import Role
from auth_service.schemas.common_schemas import MessageResponse
from auth_service.schemas.role_schemas import (
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    RoleListResponse
)
from auth_service.schemas.user_schemas import SupabaseUser

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/roles",
    tags=["admin", "roles"],
)


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
    role_data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
) -> RoleResponse:
    """
    Create a new role. This endpoint is restricted to admin users.
    
    - **name**: Unique name for the role
    - **description**: Optional description of the role
    """
    logger.info(f"Admin user attempting to create role with name: {role_data.name}")
    
    # Check if role with the same name already exists
    query = select(Role).where(Role.name == role_data.name)
    result = await db.execute(query)
    existing_role = result.scalar_one_or_none()
    
    if existing_role:
        logger.warning(f"Role with name '{role_data.name}' already exists")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role with name '{role_data.name}' already exists"
        )
    
    # Create new role
    try:
        new_role = Role(
            name=role_data.name,
            description=role_data.description
        )
        db.add(new_role)
        await db.commit()
        await db.refresh(new_role)
        
        logger.info(f"Successfully created role: {new_role.name} with ID: {new_role.id}")
        return new_role
    except IntegrityError as e:
        await db.rollback()
        logger.error(f"Database integrity error creating role: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role could not be created due to a database constraint"
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the role"
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
    skip: int = Query(0, ge=0, description="Number of roles to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum number of roles to return"),
    search: Optional[str] = Query(None, description="Optional search term for role name"),
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
) -> RoleListResponse:
    """
    List all roles with pagination and optional search. This endpoint is restricted to admin users.
    
    - **skip**: Number of roles to skip (pagination)
    - **limit**: Maximum number of roles to return (pagination)
    - **search**: Optional search term for role name
    """
    logger.info(f"Admin user retrieving roles list with skip={skip}, limit={limit}, search={search}")
    
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
    
    logger.info(f"Retrieved {len(roles)} roles (total: {total_count})")
    
    return RoleListResponse(
        items=roles,
        count=total_count
    )


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
    role_id: uuid.UUID = Path(..., description="The ID of the role to retrieve"),
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
) -> RoleResponse:
    """
    Get a specific role by ID. This endpoint is restricted to admin users.
    
    - **role_id**: The unique identifier of the role to retrieve
    """
    logger.info(f"Admin user retrieving role with ID: {role_id}")
    
    # Get the role by ID
    role = await db.get(Role, role_id)
    if not role:
        logger.warning(f"Role with ID '{role_id}' not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID '{role_id}' not found"
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
    logger.info(f"Admin user attempting to update role with ID: {role_id}")
    
    # Validate that at least one field is provided for update
    if not role_data.name and role_data.description is None:
        logger.warning("No update fields provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided for update"
        )
    
    # Get the role by ID
    role = await db.get(Role, role_id)
    if not role:
        logger.warning(f"Role with ID '{role_id}' not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID '{role_id}' not found"
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
                detail=f"Role with name '{role_data.name}' already exists"
            )
    
    # Update role fields
    try:
        if role_data.name:
            role.name = role_data.name
        if role_data.description is not None:  # Allow empty string to clear description
            role.description = role_data.description
        
        await db.commit()
        await db.refresh(role)
        
        logger.info(f"Successfully updated role with ID: {role_id}")
        return role
    except IntegrityError as e:
        await db.rollback()
        logger.error(f"Database integrity error updating role: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role could not be updated due to a database constraint"
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the role"
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
    role_id: uuid.UUID = Path(..., description="The ID of the role to delete"),
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
) -> MessageResponse:
    """
    Delete a role. This endpoint is restricted to admin users.
    
    - **role_id**: The unique identifier of the role to delete
    """
    logger.info(f"Admin user attempting to delete role with ID: {role_id}")
    
    # Get the role by ID
    role = await db.get(Role, role_id)
    if not role:
        logger.warning(f"Role with ID '{role_id}' not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID '{role_id}' not found"
        )
    
    role_name = role.name  # Store for logging
    
    try:
        # Delete the role
        await db.delete(role)
        await db.commit()
        logger.info(f"Successfully deleted role '{role_name}' with ID: {role_id}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting role '{role_name}' with ID {role_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the role"
        )
    
    return MessageResponse(message=f"Role '{role_name}' successfully deleted")
