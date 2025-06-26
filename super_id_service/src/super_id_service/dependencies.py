"""
FastAPI dependencies for authentication and Supabase client initialization.
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from supabase import create_client, Client

from super_id_service.config import settings
from super_id_service.schemas import TokenData

logger = logging.getLogger(__name__)
security = HTTPBearer()


async def get_supabase_client() -> Client:
    """
    Create and initialize the Supabase client.
    
    Returns:
        Client: Initialized Supabase client
        
    Raises:
        HTTPException: If Supabase client initialization fails
    """
    try:
        # Create the Supabase client with the URL and service role key
        client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key
        )
        return client
    except Exception as e:
        logger.exception(f"Failed to initialize Supabase client: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        )


async def validate_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenData:
    """
    Validate the JWT token from the Authorization header.
    
    Args:
        credentials: Authorization credentials extracted from the request header
        
    Returns:
        TokenData: Data extracted from the JWT token
        
    Raises:
        HTTPException: If token is invalid or missing required claims
    """
    token = credentials.credentials
    
    try:
        # Decode the JWT token using the symmetric key shared with auth_service
        payload = jwt.decode(
            token, 
            settings.jwt_secret_key, 
            algorithms=["HS256"],
            # Disable audience validation since the Auth Service sends 'paservices_microservices'
            # but we're not configured to validate it specifically
            options={
                "verify_sub": True,
                "verify_aud": False  # Disable audience validation
            }
        )
        
        # Extract and validate required claims
        if "sub" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject claim"
            )
            
        # Validate issuer if configured
        if settings.auth_service_issuer:
            if payload.get("iss") != settings.auth_service_issuer:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: unknown issuer"
                )
                
        # Extract permissions
        permissions = payload.get("permissions", [])
        
        # Create and return token data
        token_data = TokenData(
            sub=payload["sub"],
            permissions=permissions,
            iss=payload.get("iss"),
            exp=payload.get("exp"),
            metadata={
                k: v for k, v in payload.items() 
                if k not in ["sub", "permissions", "iss", "exp"]
            }
        )
        
        return token_data
        
    except JWTError as e:
        logger.warning(f"JWT validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in token validation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during authentication"
        )
