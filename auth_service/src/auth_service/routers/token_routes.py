import logging
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.config import settings
from auth_service.db import get_db
from auth_service.models.app_client import AppClient
from auth_service.models.role import Role
from auth_service.models.permission import Permission
from auth_service.rate_limiting import limiter, TOKEN_LIMIT
from auth_service.schemas.app_client_schemas import AppClientTokenRequest, AccessTokenResponse
from auth_service.schemas.common_schemas import MessageResponse
from auth_service.security import verify_client_secret, create_m2m_access_token
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Token Acquisition"],
)


@router.post(
    "/token",
    response_model=AccessTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtain an access token using client credentials",
    description="""
    Implements the OAuth 2.0 Client Credentials grant flow for machine-to-machine (M2M) authentication.
    
    This endpoint allows authorized application clients to obtain JWT access tokens for API access.
    The token contains claims about the client's identity and permissions, which are used for
    authorization decisions by protected resources.
    """,
    responses={
        status.HTTP_200_OK: {
            "description": "Successfully generated access token",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_type": "Bearer",
                        "expires_in": 900
                    }
                }
            }
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid request parameters",
            "model": MessageResponse,
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid grant_type. Only 'client_credentials' is supported."
                    }
                }
            }
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication failed",
            "model": MessageResponse,
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid client credentials."
                    }
                }
            }
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "description": "Rate limit exceeded",
            "model": MessageResponse,
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Too many requests",
                        "retry_after": 60
                    }
                }
            }
        },
    },
)
@limiter.limit(TOKEN_LIMIT, key_func=lambda request: request.client.host)
async def get_client_token(
    request: Request,
    token_request: AppClientTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> AccessTokenResponse:
    """
    Obtain an access token using client credentials. This endpoint implements the OAuth2 client credentials grant type.
    
    ## Request Parameters
    - **grant_type**: Must be 'client_credentials'. No other grant types are currently supported.
    - **client_id**: The UUID of the registered application client.
    - **client_secret**: The secret key associated with the client. Must match the stored hashed value.
    
    ## Response
    Returns a JSON object containing:
    - **access_token**: A JWT token containing the client's identity and permissions.
    - **token_type**: Always 'Bearer'.
    - **expires_in**: Number of seconds until the token expires (typically 900 seconds / 15 minutes).
    
    ## Token Claims
    The JWT token contains the following claims:
    - Standard claims: iss, sub, aud, exp, iat, jti
    - Custom claims: client_name, client_type, roles, permissions
    
    ## Error Handling
    - Returns 400 for invalid grant_type
    - Returns 401 for invalid client credentials or inactive clients
    - Returns 429 when rate limits are exceeded
    
    ## Rate Limiting
    This endpoint is rate-limited to prevent abuse. The default limit is configurable via environment variables.
    
    ## Security Notes
    - Client secrets should be treated as sensitive credentials and never exposed in client-side code
    - The resulting access token should be transmitted only over HTTPS
    - Tokens have a limited lifetime and should be refreshed as needed
    """
    # Validate grant type
    if token_request.grant_type != "client_credentials":
        logger.warning(f"Invalid grant_type '{token_request.grant_type}' provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid grant_type. Only 'client_credentials' is supported.",
        )
    
    # Find the client by ID
    try:
        client_id_uuid = uuid.UUID(token_request.client_id)
    except ValueError:
        logger.warning(f"Invalid client_id format: {token_request.client_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials.",
        )
    
    client = await db.get(AppClient, client_id_uuid)
    if not client:
        logger.warning(f"Client ID '{token_request.client_id}' not found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials.",
        )
    
    # Check if client is active
    if not client.is_active:
        logger.warning(f"Client ID '{token_request.client_id}' is inactive")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Client is inactive.",
        )
    
    # Verify client secret
    if not verify_client_secret(token_request.client_secret, client.client_secret_hash):
        logger.warning(f"Invalid client secret for client ID '{token_request.client_id}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials.",
        )
    
    # Get client's roles and permissions
    # Get app client roles
    from sqlalchemy import select
    from auth_service.models.app_client_role import AppClientRole
    
    # Query for roles associated with this client
    role_query = select(Role).join(
        AppClientRole, Role.id == AppClientRole.role_id
    ).where(AppClientRole.app_client_id == client.id)
    
    result = await db.execute(role_query)
    client_roles = result.scalars().all()
    
    # Extract role names
    role_names = [role.name for role in client_roles]
    
    # Query for permissions associated with these roles
    permissions = set()
    if client_roles:
        role_ids = [role.id for role in client_roles]
        
        # Get permissions for these roles
        from auth_service.models.role_permission import RolePermission
        
        permission_query = select(Permission).join(
            RolePermission, Permission.id == RolePermission.permission_id
        ).where(RolePermission.role_id.in_(role_ids))
        
        perm_result = await db.execute(permission_query)
        perms = perm_result.scalars().all()
        
        # Add permission names to the set
        permissions = {perm.name for perm in perms}
    
    # Create access token
    token_expiry_minutes = settings.m2m_jwt_access_token_expire_minutes
    token_expiry_seconds = token_expiry_minutes * 60  # Convert to seconds for the response
    expires_delta = timedelta(minutes=token_expiry_minutes)
    
    token = create_m2m_access_token(
        client_id=str(client.id),
        roles=role_names,
        permissions=list(permissions),
        expires_delta=expires_delta
    )
    
    logger.info(f"Generated token for client ID '{token_request.client_id}'")
    
    return AccessTokenResponse(
        access_token=token,
        token_type="Bearer",
        expires_in=token_expiry_seconds,
    )
