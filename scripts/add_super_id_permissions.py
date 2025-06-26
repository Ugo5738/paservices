#!/usr/bin/env python3
"""
Script to add the super_id:generate permission to the database
and assign it to the dev_client OAuth client.
"""

import asyncio
import logging
import os
import sys
import uuid
from typing import List, Optional
from uuid import UUID

# Add the project root to the Python path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from auth_service.config import settings
from auth_service.database import get_async_session
from auth_service.models.app_client import AppClient
from auth_service.models.permission import Permission
from auth_service.models.role import Role
from auth_service.models.app_client_role import AppClientRole
from auth_service.models.role_permission import RolePermission
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def add_permission_if_not_exists(
    db: AsyncSession, name: str, description: str = None
) -> Permission:
    """Add a permission if it doesn't already exist."""
    query = select(Permission).where(Permission.name == name)
    result = await db.execute(query)
    permission = result.scalar_one_or_none()

    if permission:
        logger.info(f"Permission '{name}' already exists.")
        return permission

    # Create new permission
    permission = Permission(
        name=name, 
        description=description or f"Permission to {name.replace(':', ' ')}"
    )
    db.add(permission)
    try:
        await db.flush()
        logger.info(f"Added permission: {name}")
        return permission
    except IntegrityError:
        await db.rollback()
        # Handle race condition - permission might have been created between our check and insert
        query = select(Permission).where(Permission.name == name)
        result = await db.execute(query)
        permission = result.scalar_one_or_none()
        if not permission:
            logger.error(f"Failed to create permission: {name}")
            raise
        return permission


async def add_role_if_not_exists(
    db: AsyncSession, name: str, description: str = None
) -> Role:
    """Add a role if it doesn't already exist."""
    query = select(Role).where(Role.name == name)
    result = await db.execute(query)
    role = result.scalar_one_or_none()

    if role:
        logger.info(f"Role '{name}' already exists.")
        return role

    # Create new role
    role = Role(
        name=name,
        description=description or f"Role for {name.lower().replace('_', ' ')}"
    )
    db.add(role)
    try:
        await db.flush()
        logger.info(f"Added role: {name}")
        return role
    except IntegrityError:
        await db.rollback()
        # Handle race condition
        query = select(Role).where(Role.name == name)
        result = await db.execute(query)
        role = result.scalar_one_or_none()
        if not role:
            logger.error(f"Failed to create role: {name}")
            raise
        return role


async def assign_permissions_to_role(
    db: AsyncSession, role: Role, permissions: List[Permission]
) -> None:
    """Assign permissions to a role."""
    for permission in permissions:
        # Check if the role already has this permission
        query = select(RolePermission).where(
            RolePermission.role_id == role.id,
            RolePermission.permission_id == permission.id
        )
        result = await db.execute(query)
        role_permission = result.scalar_one_or_none()

        if role_permission:
            logger.info(f"Role '{role.name}' already has permission '{permission.name}'")
            continue

        # Assign the permission to the role
        role_permission = RolePermission(
            role_id=role.id,
            permission_id=permission.id
        )
        db.add(role_permission)
        try:
            await db.flush()
            logger.info(f"Assigned permission '{permission.name}' to role '{role.name}'")
        except IntegrityError:
            await db.rollback()
            logger.warning(f"Failed to assign permission '{permission.name}' to role '{role.name}'")


async def assign_role_to_client(
    db: AsyncSession, client_id_str: str, role: Role
) -> None:
    """Assign a role to an OAuth client."""
    # Generate the deterministic UUID from the client ID string
    # Use the same namespace as in the test_rightmove_flow.py script
    client_id = uuid.uuid5(uuid.NAMESPACE_DNS, client_id_str)
    
    # Verify the client exists
    query = select(AppClient).where(AppClient.id == client_id)
    result = await db.execute(query)
    client = result.scalar_one_or_none()
    
    if not client:
        logger.error(f"Client with ID '{client_id}' not found.")
        return None

    # Check if the client already has this role
    query = select(AppClientRole).where(
        AppClientRole.app_client_id == client.id,
        AppClientRole.role_id == role.id
    )
    result = await db.execute(query)
    client_role = result.scalar_one_or_none()

    if client_role:
        logger.info(f"Client '{client_id_str}' already has role '{role.name}'")
        return

    # Assign the role to the client
    client_role = AppClientRole(
        app_client_id=client.id,
        role_id=role.id
    )
    db.add(client_role)
    try:
        await db.flush()
        logger.info(f"Assigned role '{role.name}' to client '{client_id_str}'")
    except IntegrityError:
        await db.rollback()
        logger.warning(f"Failed to assign role '{role.name}' to client '{client_id_str}'")


async def main() -> None:
    """Main entry point to add permissions and assign to client."""
    client_id = "dev_client"  # This must match the client ID used in test_rightmove_flow.py
    
    # Create an async database session
    async for db in get_async_session():
        try:
            # Begin transaction
            await db.begin()
            
            # 1. Create the required permission
            permission = await add_permission_if_not_exists(
                db, 
                name="super_id:generate",
                description="Permission to generate Super IDs"
            )
            
            # 2. Create a role for microservices
            role = await add_role_if_not_exists(
                db,
                name="MICROSERVICE",
                description="Role for internal microservice communication"
            )
            
            # 3. Assign the permission to the role
            await assign_permissions_to_role(db, role, [permission])
            
            # 4. Assign the role to the client
            await assign_role_to_client(db, client_id, role)
            
            # Commit all changes
            await db.commit()
            logger.info("Successfully added permissions and roles to the client")
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error setting up permissions: {str(e)}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
