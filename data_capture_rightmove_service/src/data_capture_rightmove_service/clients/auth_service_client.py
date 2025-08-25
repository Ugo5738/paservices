"""
Auth Service Client for acquiring M2M tokens to authenticate with other services.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

import httpx

from data_capture_rightmove_service.config import settings

logger = logging.getLogger(__name__)


def print_color(text, color):
    colors = {
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "reset": "\033[0m",
    }
    print(f"{colors.get(color, '')}{text}{colors['reset']}")


class AuthServiceClient:
    """
    Client for interacting with the Auth Service API for M2M authentication.
    Handles token acquisition and caching to avoid unnecessary API calls.
    """

    def __init__(self, base_url: str = None):
        """
        Initialize the Auth Service Client.

        Args:
            base_url: Base URL for the Auth Service API, defaults to the value in settings
        """
        self.base_url = base_url or settings.AUTH_SERVICE_URL
        self.client_id = settings.M2M_CLIENT_ID
        self.client_secret = settings.M2M_CLIENT_SECRET

        # Token cache
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    async def get_token(self, force_refresh: bool = False) -> str:
        """
        Get an M2M JWT token for authenticating with other services.
        If a valid token exists in the cache, return it, otherwise fetch a new one.

        Args:
            force_refresh: Force token refresh even if the current token is still valid

        Returns:
            str: The JWT token to use for authentication

        Raises:
            HTTPException: If token acquisition fails
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
        logger.info(f"Auth Service Client is attempting to connect to: {url}")
        print_color(f"DEBUG: Connecting to Auth Service at URL: {url}", "magenta")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/auth/token",
                    json={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "client_credentials",  # Required by OAuth2 spec
                    },
                    timeout=10.0,
                )

                response.raise_for_status()
                data = response.json()

                self._token = data["access_token"]
                # Set expiry 1 minute before actual expiry to avoid edge cases
                expires_in = data.get("expires_in", 1800)  # Default to 30 minutes
                self._token_expiry = datetime.utcnow() + timedelta(
                    seconds=expires_in - 60
                )

                logger.info(
                    f"Successfully acquired new M2M token, valid until {self._token_expiry}"
                )
                return self._token
        except httpx.HTTPError as e:
            logger.error(f"Failed to acquire M2M token: {str(e)}")
            # Clear token cache in case of error
            self._token = None
            self._token_expiry = None
            raise

    async def get_auth_header(self, force_refresh: bool = False) -> Dict[str, str]:
        """
        Get the Authorization header with a valid JWT token.

        Args:
            force_refresh: Force token refresh even if the current token is still valid

        Returns:
            Dict[str, str]: Header with Authorization Bearer token
        """
        token = await self.get_token(force_refresh=force_refresh)
        return {"Authorization": f"Bearer {token}"}


# Create a global instance of the auth service client
auth_service_client = AuthServiceClient()
