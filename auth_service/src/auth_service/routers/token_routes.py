import base64
import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from jwcrypto import jwk
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_db
from ..helpers.token_logic import generate_client_token
from ..schemas.app_client_schemas import AccessTokenResponse, AppClientTokenRequest
from ..schemas.common_schemas import MessageResponse
from ..utils.logging_config import logger
from ..utils.rate_limiting import TOKEN_LIMIT, limiter

router = APIRouter(
    prefix="/auth",
    tags=["Token Acquisition"],
)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_PUBLIC_KEY_PATH = os.path.join(_BASE_DIR, "..", "keys", "public.pem")


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


@router.post(
    "/token",
    response_model=AccessTokenResponse,
    status_code=status.HTTP_200_OK,
    operation_id="create_m2m_token",
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
                        "expires_in": 900,
                    }
                }
            },
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
            },
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication failed",
            "model": MessageResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid client credentials."}
                }
            },
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "description": "Rate limit exceeded",
            "model": MessageResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Too many requests", "retry_after": 60}
                }
            },
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
    # Inbound request logging (strict redaction, no secrets/tokens)
    try:
        logger.info(
            "Inbound request: token issuance",
            extra={
                "request": {
                    "method": request.method,
                    "path": request.url.path,
                    "client_host": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent"),
                },
                "body_excerpt": _redact_sensitive(token_request.model_dump()),
            },
        )
    except Exception:
        # Never block token path due to logging
        pass

    # Validate grant type
    if token_request.grant_type != "client_credentials":
        logger.warning(f"Invalid grant_type '{token_request.grant_type}' provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid grant_type. Only 'client_credentials' is supported.",
        )

    # The entire complex logic is now replaced with a single call
    token_data = await generate_client_token(
        db, token_request.client_id, token_request.client_secret
    )

    logger.info(
        "Outbound response: token issuance",
        extra={
            "status": status.HTTP_200_OK,
            "client_id": token_request.client_id,
            "expires_in": token_data["expires_in"],
        },
    )

    return AccessTokenResponse(**token_data)


@router.get("/.well-known/jwks.json")
async def jwks():
    # Load public key
    with open(_PUBLIC_KEY_PATH, "rb") as f:
        pub = jwk.JWK.from_pem(f.read())

    # Dump as JWKS
    jwks = {"keys": [pub.export(as_dict=True)]}
    jwks["keys"][0]["alg"] = settings.M2M_JWT_ALGORITHM
    jwks["keys"][0]["use"] = "sig"
    jwks["keys"][0]["kid"] = settings.M2M_JWT_KID

    return JSONResponse(jwks)
