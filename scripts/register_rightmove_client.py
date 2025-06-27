#!/usr/bin/env python
"""
Script to register a new machine-to-machine client for the data_capture_rightmove_service
with permissions to call the Super ID service.

This script must be run with a connection to the auth service database.
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime

import bcrypt
from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    selectinload,
    sessionmaker,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Get database URL from environment variable or use default
DB_URL = os.environ.get("AUTH_SERVICE_DATABASE_URL")
if not DB_URL:
    logger.error("AUTH_SERVICE_DATABASE_URL environment variable is not set")
    exit(1)

# Ensure URL is async compatible
if DB_URL.startswith("postgresql://"):
    ASYNC_DB_URL = DB_URL.replace("postgresql://", "postgresql+asyncpg://")
else:
    ASYNC_DB_URL = DB_URL


# SQLAlchemy models (simplified versions of auth service models)
class Base(DeclarativeBase):
    pass


class AppClient(Base):
    __tablename__ = "app_clients"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(nullable=False)
    client_id: Mapped[str] = mapped_column(nullable=False, unique=True)
    client_secret_hash: Mapped[str] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    description: Mapped[str] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    roles = relationship("AppClientRole", back_populates="app_client")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(nullable=False, unique=True)
    description: Mapped[str] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    app_clients = relationship("AppClientRole", back_populates="role")
    permissions = relationship("RolePermission", back_populates="role")


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(nullable=False, unique=True)
    description: Mapped[str] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    roles = relationship("RolePermission", back_populates="permission")


class AppClientRole(Base):
    __tablename__ = "app_client_roles"

    app_client_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    role_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    app_client = relationship("AppClient", back_populates="roles")
    role = relationship("Role", back_populates="app_clients")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    permission_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="roles")


# Create a session factory
async_engine = create_async_engine(ASYNC_DB_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# Helper functions
def hash_client_secret(secret: str) -> str:
    """Generate a bcrypt hash of the client secret."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(secret.encode("utf-8"), salt)
    return hashed.decode("utf-8")


async def create_super_id_permission_if_not_exists(db: AsyncSession) -> Permission:
    """Create the Super ID generate permission if it doesn't exist."""
    super_id_permission_name = "super_id:generate"

    # Check if permission exists
    result = await db.execute(
        select(Permission).where(Permission.name == super_id_permission_name)
    )
    permission = result.scalars().first()

    if not permission:
        logger.info(f"Creating permission: {super_id_permission_name}")
        permission = Permission(
            name=super_id_permission_name,
            description="Permission to generate Super IDs via the Super ID Service",
        )
        db.add(permission)
        await db.commit()
        await db.refresh(permission)

    return permission


async def create_rightmove_service_role_if_not_exists(
    db: AsyncSession, permission: Permission
) -> Role:
    """Create a role for the Rightmove service if it doesn't exist."""
    role_name = "rightmove_service_role"

    # Check if role exists
    result = await db.execute(select(Role).where(Role.name == role_name))
    role = result.scalars().first()

    if not role:
        logger.info(f"Creating role: {role_name}")
        role = Role(
            name=role_name,
            description="Role for the Rightmove Data Capture Service with Super ID permissions",
        )
        db.add(role)
        await db.flush()

        # Attach permission to role
        role_permission = RolePermission(role_id=role.id, permission_id=permission.id)
        db.add(role_permission)

        await db.commit()
        await db.refresh(role)
    else:
        # Check if permission is already attached to role
        result = await db.execute(
            select(RolePermission).where(
                RolePermission.role_id == role.id,
                RolePermission.permission_id == permission.id,
            )
        )
        role_permission = result.scalars().first()

        if not role_permission:
            logger.info(f"Attaching permission {permission.name} to role {role.name}")
            role_permission = RolePermission(
                role_id=role.id, permission_id=permission.id
            )
            db.add(role_permission)
            await db.commit()

    return role


async def register_rightmove_client(db: AsyncSession, role: Role) -> AppClient:
    """Register a new client for the Rightmove service."""
    client_id = "rightmove-data-capture-service"
    client_name = "Data Capture Rightmove Service"

    # Check if client already exists
    result = await db.execute(select(AppClient).where(AppClient.client_id == client_id))
    client = result.scalars().first()

    if client:
        logger.info(f"Client {client_id} already exists, generating new client secret")
        # Generate a new client secret
        client_secret = str(uuid.uuid4())
        client.client_secret_hash = hash_client_secret(client_secret)
        await db.commit()
        await db.refresh(client)

        logger.info(f"Updated client secret for {client_id}")
        logger.info(f"CLIENT_ID: {client_id}")
        logger.info(f"CLIENT_SECRET: {client_secret}")
    else:
        # Create a new client
        client_secret = str(uuid.uuid4())
        client = AppClient(
            name=client_name,
            client_id=client_id,
            client_secret_hash=hash_client_secret(client_secret),
            description="Machine-to-machine client for the Rightmove Data Capture Service",
        )
        db.add(client)
        await db.flush()

        # Attach role to client
        client_role = AppClientRole(app_client_id=client.id, role_id=role.id)
        db.add(client_role)

        await db.commit()
        await db.refresh(client)

        logger.info(f"Created new client {client_id}")
        logger.info(f"CLIENT_ID: {client_id}")
        logger.info(f"CLIENT_SECRET: {client_secret}")

    return client, client_secret


async def main():
    """Main execution function."""
    logger.info("Starting client registration for Rightmove Data Capture Service")

    async with AsyncSessionLocal() as db:
        # Create permission if it doesn't exist
        permission = await create_super_id_permission_if_not_exists(db)
        logger.info(f"Permission: {permission.name}")

        # Create role if it doesn't exist
        role = await create_rightmove_service_role_if_not_exists(db, permission)
        logger.info(f"Role: {role.name}")

        # Register client
        client, client_secret = await register_rightmove_client(db, role)

        logger.info("Client registration complete")
        logger.info("========== SAVE THESE CREDENTIALS ==========")
        logger.info(f"CLIENT_ID: {client.client_id}")
        logger.info(f"CLIENT_SECRET: {client_secret}")
        logger.info("===========================================")
        logger.info("Add the following to your .env.dev file:")
        logger.info(f"DATA_CAPTURE_RIGHTMOVE_SERVICE_M2M_CLIENT_ID={client.client_id}")
        logger.info(f"DATA_CAPTURE_RIGHTMOVE_SERVICE_M2M_CLIENT_SECRET={client_secret}")


if __name__ == "__main__":
    asyncio.run(main())
