#!/usr/bin/env python3
"""
Simplified script to add the super_id:generate permission to the dev_client
"""

import asyncio
import logging
import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Import directly from the auth_service src structure
from src.auth_service.database import get_async_session
from src.auth_service.models.app_client import AppClient
from src.auth_service.models.permission import Permission
from src.auth_service.models.role import Role
from src.auth_service.models.app_client_role import AppClientRole
from src.auth_service.models.role_permission import RolePermission

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    client_id_str = "dev_client"
    permission_name = "super_id:generate"
    role_name = "MICROSERVICE"
    
    client_id = uuid.uuid5(uuid.NAMESPACE_DNS, client_id_str)
    logger.info(f"Adding permission '{permission_name}' to client '{client_id_str}' (UUID: {client_id})")
    
    async for db in get_async_session():
        await db.begin()
        try:
            # 1. Verify the client exists
            client_query = select(AppClient).where(AppClient.id == client_id)
            client_result = await db.execute(client_query)
            client = client_result.scalar_one_or_none()
            
            if not client:
                logger.error(f"Client with ID '{client_id}' not found.")
                return
                
            logger.info(f"Found client: {client.id} - {client.client_name}")
            
            # 2. Create or get the permission
            perm_query = select(Permission).where(Permission.name == permission_name)
            perm_result = await db.execute(perm_query)
            permission = perm_result.scalar_one_or_none()
            
            if not permission:
                permission = Permission(
                    name=permission_name,
                    description=f"Permission to generate Super IDs"
                )
                db.add(permission)
                await db.flush()
                logger.info(f"Created permission: {permission_name}")
            else:
                logger.info(f"Permission '{permission_name}' already exists.")
            
            # 3. Create or get the role
            role_query = select(Role).where(Role.name == role_name)
            role_result = await db.execute(role_query)
            role = role_result.scalar_one_or_none()
            
            if not role:
                role = Role(
                    name=role_name,
                    description="Role for internal microservice communication"
                )
                db.add(role)
                await db.flush()
                logger.info(f"Created role: {role_name}")
            else:
                logger.info(f"Role '{role_name}' already exists.")
            
            # 4. Assign permission to role (if not already assigned)
            role_perm_query = select(RolePermission).where(
                RolePermission.role_id == role.id,
                RolePermission.permission_id == permission.id
            )
            role_perm_result = await db.execute(role_perm_query)
            role_perm = role_perm_result.scalar_one_or_none()
            
            if not role_perm:
                role_perm = RolePermission(
                    role_id=role.id,
                    permission_id=permission.id
                )
                db.add(role_perm)
                await db.flush()
                logger.info(f"Assigned permission '{permission_name}' to role '{role_name}'")
            else:
                logger.info(f"Permission '{permission_name}' already assigned to role '{role_name}'")
            
            # 5. Assign role to client (if not already assigned)
            client_role_query = select(AppClientRole).where(
                AppClientRole.app_client_id == client.id,
                AppClientRole.role_id == role.id
            )
            client_role_result = await db.execute(client_role_query)
            client_role = client_role_result.scalar_one_or_none()
            
            if not client_role:
                client_role = AppClientRole(
                    app_client_id=client.id,
                    role_id=role.id
                )
                db.add(client_role)
                await db.flush()
                logger.info(f"Assigned role '{role_name}' to client '{client_id_str}'")
            else:
                logger.info(f"Role '{role_name}' already assigned to client '{client_id_str}'")
            
            await db.commit()
            logger.info("Successfully added all permissions and role assignments")
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error: {str(e)}")
            raise

if __name__ == "__main__":
    asyncio.run(main())
