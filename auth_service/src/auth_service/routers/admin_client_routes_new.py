import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.db import get_db
from auth_service.dependencies.user_deps import require_admin_user
from auth_service.models.app_client import AppClient
from auth_service.models.role import Role
# from auth_service.models.app_client_role_model import AppClientRole # Not directly used for creation here
from auth_service.schemas.app_client_schemas import (
    AppClientCreateRequest,
    AppClientCreatedResponse,
    AppClientResponse,
    AppClientListResponse,
    AppClientUpdateRequest,
)
from auth_service.schemas.common_schemas import MessageResponse
from auth_service.schemas.user_schemas import SupabaseUser # For type hinting require_admin_user
from auth_service.security import generate_client_secret, hash_secret

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth/admin/clients",
    tags=["Admin - App Clients"],
    dependencies=[Depends(require_admin_user)],
)


@router.post(
    "",
    response_model=AppClientCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new application client",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": MessageResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": MessageResponse},
        status.HTTP_403_FORBIDDEN: {"model": MessageResponse},
        status.HTTP_409_CONFLICT: {"model": MessageResponse},
    },
)
async def create_app_client(
    client_data: AppClientCreateRequest,
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user), # Ensures admin access
) -> AppClientCreatedResponse:
    """
    Create a new application client. This endpoint is restricted to admin users.

    - **client_name**: Unique name for the client.
    - **description**: Optional description.
    - **allowed_callback_urls**: Optional list of callback URLs.
    - **assigned_roles**: Optional list of role names to assign to the client.
    """
    logger.info(f"Admin user attempting to create app client: {client_data.client_name}")

    # Check if client name already exists
    existing_client_stmt = select(AppClient).where(AppClient.client_name == client_data.client_name)
    result = await db.execute(existing_client_stmt)
    if result.scalars().first():
        logger.warning(f"App client name '{client_data.client_name}' already exists.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"App client with name '{client_data.client_name}' already exists.",
        )

    client_id = uuid.uuid4()
    plain_client_secret = generate_client_secret()
    hashed_client_secret = hash_secret(plain_client_secret)

    new_client = AppClient(
        id=client_id,
        client_name=client_data.client_name,
        client_secret_hash=hashed_client_secret,
        description=client_data.description,
        allowed_callback_urls=client_data.allowed_callback_urls,
        is_active=True, # Active by default
    )

    # Handle assigned roles
    client_roles = []
    if client_data.assigned_roles:
        for role_name in client_data.assigned_roles:
            role_stmt = select(Role).where(Role.name == role_name)
            role_result = await db.execute(role_stmt)
            role = role_result.scalars().first()
            if not role:
                logger.warning(f"Role '{role_name}' not found while creating app client '{client_data.client_name}'.")
                # Depending on strictness, could raise 400 or just skip
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Role '{role_name}' not found."
                )
            client_roles.append(role)
        new_client.roles = client_roles

    try:
        db.add(new_client)
        await db.commit()
        await db.refresh(new_client)
        logger.info(f"Successfully created app client '{new_client.client_name}' with ID: {new_client.id}")
    except IntegrityError as e:
        await db.rollback()
        logger.error(f"Database integrity error creating app client '{client_data.client_name}': {e}")
        # This might happen if a unique constraint is violated concurrently, though name check is done above.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create app client due to a database error.",
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected error creating app client '{client_data.client_name}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the app client.",
        )

    return AppClientCreatedResponse(
        client_id=str(new_client.id),  # Convert UUID to string to match Pydantic model
        client_secret=plain_client_secret, # Return plain secret ONLY on creation
        client_name=new_client.client_name,
        description=new_client.description,
        allowed_callback_urls=new_client.allowed_callback_urls if new_client.allowed_callback_urls else [],
        assigned_roles=[role.name for role in new_client.roles] if new_client.roles else [],
        is_active=new_client.is_active,
        created_at=new_client.created_at,
        updated_at=new_client.updated_at,
    )


@router.get(
    "",
    response_model=AppClientListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all application clients",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": MessageResponse},
        status.HTTP_403_FORBIDDEN: {"model": MessageResponse},
    },
)
async def list_app_clients(
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum number of items to return"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
) -> AppClientListResponse:
    """
    List all application clients. This endpoint is restricted to admin users.
    
    - **skip**: Number of items to skip (pagination).
    - **limit**: Maximum number of items to return (pagination).
    - **is_active**: Optional filter for active status.
    """
    logger.info(f"Admin user retrieving list of app clients with params: skip={skip}, limit={limit}, is_active={is_active}")
    
    # Build query
    query = select(AppClient)
    
    # Apply filters if provided
    if is_active is not None:
        query = query.where(AppClient.is_active == is_active)
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    clients = result.scalars().all()
    
    # Get total count for pagination info
    count_query = select(AppClient)
    if is_active is not None:
        count_query = count_query.where(AppClient.is_active == is_active)
    count_result = await db.execute(count_query)
    total_count = len(count_result.scalars().all())  # This is not the most efficient way, but it works for now
    
    # Prepare response data
    client_list = []
    for client in clients:
        await db.refresh(client, ["roles"])
        client_list.append(AppClientResponse(
            client_id=str(client.id),
            client_name=client.client_name,
            description=client.description,
            allowed_callback_urls=client.allowed_callback_urls if client.allowed_callback_urls else [],
            assigned_roles=[role.name for role in client.roles] if client.roles else [],
            is_active=client.is_active,
            created_at=client.created_at,
            updated_at=client.updated_at,
        ))
    
    return AppClientListResponse(clients=client_list, count=total_count)


@router.get(
    "/{client_id}",
    response_model=AppClientResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a specific application client",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": MessageResponse},
        status.HTTP_403_FORBIDDEN: {"model": MessageResponse},
        status.HTTP_404_NOT_FOUND: {"model": MessageResponse},
    },
)
async def get_app_client(
    client_id: uuid.UUID = Path(..., description="The ID of the app client to retrieve"),
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
) -> AppClientResponse:
    """
    Get a specific application client by ID. This endpoint is restricted to admin users.
    
    - **client_id**: The unique identifier of the app client to retrieve.
    """
    logger.info(f"Admin user retrieving app client with ID: {client_id}")
    
    # Get the client by ID
    client = await db.get(AppClient, client_id)
    if not client:
        logger.warning(f"App client with ID '{client_id}' not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App client with ID '{client_id}' not found.",
        )
    
    # Refresh to get relationships
    await db.refresh(client, ["roles"])
    
    return AppClientResponse(
        client_id=str(client.id),
        client_name=client.client_name,
        description=client.description,
        allowed_callback_urls=client.allowed_callback_urls if client.allowed_callback_urls else [],
        assigned_roles=[role.name for role in client.roles] if client.roles else [],
        is_active=client.is_active,
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


@router.put(
    "/{client_id}",
    response_model=AppClientResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an application client",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": MessageResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": MessageResponse},
        status.HTTP_403_FORBIDDEN: {"model": MessageResponse},
        status.HTTP_404_NOT_FOUND: {"model": MessageResponse},
        status.HTTP_409_CONFLICT: {"model": MessageResponse},
    },
)
async def update_app_client(
    client_data: AppClientUpdateRequest,
    client_id: uuid.UUID = Path(..., description="The ID of the app client to update"),
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
) -> AppClientResponse:
    """
    Update an application client. This endpoint is restricted to admin users.
    
    - **client_id**: The unique identifier of the app client to update.
    - **client_name**: New name for the client (optional).
    - **description**: New description (optional).
    - **allowed_callback_urls**: New list of allowed callback URLs (optional).
    - **is_active**: New active status (optional).
    """
    logger.info(f"Admin user attempting to update app client with ID: {client_id}")
    
    # Get the client by ID
    client = await db.get(AppClient, client_id)
    if not client:
        logger.warning(f"App client with ID '{client_id}' not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App client with ID '{client_id}' not found.",
        )
    
    # Check if the new client_name already exists (if provided)
    if client_data.client_name is not None and client_data.client_name != client.client_name:
        existing_client_stmt = select(AppClient).where(AppClient.client_name == client_data.client_name)
        result = await db.execute(existing_client_stmt)
        if result.scalars().first():
            logger.warning(f"App client name '{client_data.client_name}' already exists.")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"App client with name '{client_data.client_name}' already exists.",
            )
    
    # Update the client attributes if provided
    update_data = {}
    if client_data.client_name is not None:
        update_data["client_name"] = client_data.client_name
    if client_data.description is not None:
        update_data["description"] = client_data.description
    if client_data.allowed_callback_urls is not None:
        update_data["allowed_callback_urls"] = client_data.allowed_callback_urls
    if client_data.is_active is not None:
        update_data["is_active"] = client_data.is_active
    
    if update_data:
        try:
            # Apply updates
            for key, value in update_data.items():
                setattr(client, key, value)
            
            await db.commit()
            await db.refresh(client)
            
            # Refresh to get relationships
            await db.refresh(client, ["roles"])
            
            logger.info(f"Successfully updated app client '{client.client_name}' with ID: {client.id}")
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Database integrity error updating app client '{client.client_name}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not update app client due to a database error.",
            )
        except Exception as e:
            await db.rollback()
            logger.error(f"Unexpected error updating app client '{client.client_name}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while updating the app client.",
            )
    else:
        logger.info(f"No updates provided for app client with ID: {client_id}")
    
    return AppClientResponse(
        client_id=str(client.id),
        client_name=client.client_name,
        description=client.description,
        allowed_callback_urls=client.allowed_callback_urls if client.allowed_callback_urls else [],
        assigned_roles=[role.name for role in client.roles] if client.roles else [],
        is_active=client.is_active,
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


@router.delete(
    "/{client_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete an application client",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": MessageResponse},
        status.HTTP_403_FORBIDDEN: {"model": MessageResponse},
        status.HTTP_404_NOT_FOUND: {"model": MessageResponse},
    },
)
async def delete_app_client(
    client_id: uuid.UUID = Path(..., description="The ID of the app client to delete"),
    db: AsyncSession = Depends(get_db),
    _current_admin: SupabaseUser = Depends(require_admin_user),
) -> MessageResponse:
    """
    Delete an application client. This endpoint is restricted to admin users.
    
    - **client_id**: The unique identifier of the app client to delete.
    """
    logger.info(f"Admin user attempting to delete app client with ID: {client_id}")
    
    # Get the client by ID
    client = await db.get(AppClient, client_id)
    if not client:
        logger.warning(f"App client with ID '{client_id}' not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App client with ID '{client_id}' not found.",
        )
    
    client_name = client.client_name  # Store for logging
    
    try:
        # Delete the client
        await db.delete(client)
        await db.commit()
        logger.info(f"Successfully deleted app client '{client_name}' with ID: {client_id}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting app client '{client_name}' with ID {client_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the app client.",
        )
    
    return MessageResponse(detail=f"App client '{client_name}' successfully deleted.")
