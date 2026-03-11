"""
Auth Service Client for acquiring M2M tokens to authenticate with other services.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

import httpx

from data_capture_service.config import settings

logger = logging.getLogger(__name__)


class AuthServiceClient:
    """
    Client for interacting with the Auth Service API for M2M authentication.
    Handles token acquisition and caching to avoid unnecessary API calls.
    """

    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.AUTH_SERVICE_URL
        self.client_id = settings.M2M_CLIENT_ID
        self.client_secret = settings.M2M_CLIENT_SECRET

        # Token cache
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    async def get_token(self, force_refresh: bool = False) -> str:
        """
        Get an M2M JWT token for authenticating with other services.
        Uses cached token if still valid.
        """
        if (
            not force_refresh
            and self._token
            and self._token_expiry
            and datetime.utcnow() < self._token_expiry
        ):
            logger.debug("Using cached auth token.")
            return self._token

        logger.info("Fetching new M2M token from Auth Service")

        url = f"{self.base_url}/auth/token"
        logger.info(f"Auth Service Client connecting to: {url}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "client_credentials",
                    },
                    timeout=10.0,
                )

                response.raise_for_status()
                data = response.json()

                self._token = data["access_token"]
                expires_in = data.get("expires_in", 1800)
                self._token_expiry = datetime.utcnow() + timedelta(
                    seconds=expires_in - 60
                )

                logger.info(
                    f"Successfully acquired new M2M token, valid until {self._token_expiry}"
                )
                return self._token
        except httpx.HTTPError as e:
            logger.error(f"Failed to acquire M2M token: {str(e)}")
            self._token = None
            self._token_expiry = None
            raise

    async def get_auth_header(self, force_refresh: bool = False) -> Dict[str, str]:
        """Get the Authorization header with a valid JWT token."""
        token = await self.get_token(force_refresh=force_refresh)
        return {"Authorization": f"Bearer {token}"}


# Create a global instance of the auth service client
auth_service_client = AuthServiceClient()
