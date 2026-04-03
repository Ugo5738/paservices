"""
M2M authentication helper with token caching.

Calls the auth service to get an M2M JWT token using client_credentials grant.
Caches the token in memory and refreshes it before expiry.
"""

import time
from typing import Optional

import httpx

from ..config import settings
from ..utils.logging_config import logger

# In-memory token cache
_cached_token: Optional[str] = None
_token_expires_at: float = 0.0


async def get_m2m_token(client: Optional[httpx.AsyncClient] = None) -> str:
    """
    Get an M2M access token from the auth service, using cache when possible.

    Refreshes the token 60 seconds before expiry to avoid race conditions.
    """
    global _cached_token, _token_expires_at

    # Return cached token if still valid (with 60s buffer)
    if _cached_token and time.time() < (_token_expires_at - 60):
        return _cached_token

    if not settings.M2M_CLIENT_ID or not settings.M2M_CLIENT_SECRET:
        raise ValueError(
            "M2M credentials not configured. "
            "Set PA_MCP_M2M_CLIENT_ID and PA_MCP_M2M_CLIENT_SECRET."
        )

    url = f"{settings.AUTH_SERVICE_URL}/auth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": settings.M2M_CLIENT_ID,
        "client_secret": settings.M2M_CLIENT_SECRET,
    }

    should_close = False
    if client is None:
        client = httpx.AsyncClient()
        should_close = True

    try:
        resp = await client.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        _cached_token = data["access_token"]
        _token_expires_at = time.time() + data.get("expires_in", 3600)

        logger.info("M2M token obtained (expires in %ds)", data.get("expires_in", 0))
        return _cached_token

    except httpx.HTTPError as exc:
        logger.error("Failed to get M2M token: %s", exc, exc_info=True)
        raise RuntimeError(f"Failed to authenticate with auth service: {exc}")
    finally:
        if should_close:
            await client.aclose()
