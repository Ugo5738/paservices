# auth_service/src/auth_service/helpers/token_logic.py
import uuid
from datetime import datetime, timedelta
from typing import Dict

from fastapi import HTTPException, status
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.app_client import AppClient
from ..models.app_client_role import AppClientRole
from ..models.permission import Permission
from ..models.role import Role
from ..security import create_m2m_access_token, verify_client_secret
from ..utils.logging_config import logger


async def generate_client_token(
    db: AsyncSession, client_id_str: str, client_secret: str
) -> Dict:
    """
    Core business logic for validating client credentials and generating an M2M token.
    """
    try:
        client_id_uuid = uuid.UUID(client_id_str)
    except ValueError:
        logger.warning(f"Invalid client_id format: {client_id_str}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials.",
        )

    client = await db.get(AppClient, client_id_uuid)
    if (
        not client
        or not client.is_active
        or not verify_client_secret(client_secret, client.client_secret_hash)
    ):
        logger.warning(f"Invalid client credentials: {client_id_str}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials.",
        )

    # Fetch client's roles and permissions
    role_query = (
        select(Role).join(AppClientRole).where(AppClientRole.app_client_id == client.id)
    )
    role_result = await db.execute(role_query)
    client_roles = role_result.scalars().all()
    role_names = [role.name for role in client_roles]

    permissions = set()
    if client_roles:
        role_ids = [role.id for role in client_roles]
        from ..models.role_permission import RolePermission

        permission_query = (
            select(Permission)
            .join(RolePermission)
            .where(RolePermission.role_id.in_(role_ids))
        )
        perm_result = await db.execute(permission_query)
        permissions = {perm.name for perm in perm_result.scalars().all()}

    expires_delta = timedelta(minutes=settings.M2M_JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_m2m_access_token(
        client_id=str(client.id),
        roles=role_names,
        permissions=list(permissions),
        expires_delta=expires_delta,
    )

    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": int(expires_delta.total_seconds()),
    }
