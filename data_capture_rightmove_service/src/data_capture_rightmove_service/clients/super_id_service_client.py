"""
Super ID Service Client for generating and retrieving tracking UUIDs.
"""

import logging
import uuid
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException

from data_capture_rightmove_service.clients.auth_service_client import (
    auth_service_client,
)
from data_capture_rightmove_service.config import settings

logger = logging.getLogger(__name__)


class SuperIdServiceClient:
    """
    Client for interacting with the Super ID Service API for UUID generation and tracking.
    """

    def __init__(self, base_url: str = None):
        """
        Initialize the Super ID Service Client.

        Args:
            base_url: Base URL for the Super ID Service API, defaults to the value in settings
        """
        self.base_url = base_url or settings.SUPER_ID_SERVICE_URL
        logger.info(f"Initializing Super ID Service Client with URL: {self.base_url}")

    async def create_super_id(
        self,
        description: str = None,
        metadata: Optional[Dict[str, Any]] = None,
        source_service: str = "data_capture_rightmove_service",
    ) -> uuid.UUID:
        """
        Generate a new Super ID UUID for tracking purposes.

        This method is backwards-compatible. It can be called with a simple
        'description' or a richer 'metadata' dictionary.

        Args:
            description: Optional simple description of the workflow.
            metadata: Optional dictionary for richer metadata. If provided, it is used directly.
            source_service: The name of the service requesting the Super ID.

        Returns:
            uuid.UUID: The generated UUID

        Raises:
            HTTPException: If Super ID generation fails
        """
        try:
            # Get auth headers with a valid token
            headers = await auth_service_client.get_auth_header()

            # Construct the payload correctly. Prioritize the new 'metadata' argument,
            # but fall back to using 'description' for backwards compatibility.
            final_metadata = {}
            if metadata:
                final_metadata = metadata
            elif description:
                # If only description is provided, wrap it in a metadata object
                # to match what the super_id_service API expects.
                final_metadata = {
                    "source_service": source_service,
                    "description": description,
                }

            payload = {
                "count": 1,
                "metadata": final_metadata,
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/super_ids",
                    json=payload,
                    headers=headers,
                    timeout=10.0,
                )

                response.raise_for_status()
                data = response.json()

                # Return the UUID from the response
                return uuid.UUID(data["super_id"])

        except httpx.HTTPError as e:
            logger.error(f"Failed to generate Super ID: {str(e)}")
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 401:
                # If unauthorized, try with a fresh token
                try:
                    headers = await auth_service_client.get_auth_header(
                        force_refresh=True
                    )
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"{self.base_url}/super_ids",
                            json=payload,
                            headers=headers,
                            timeout=10.0,
                        )

                        response.raise_for_status()
                        data = response.json()

                        return uuid.UUID(data["super_id"])
                except httpx.HTTPError as retry_err:
                    logger.error(
                        f"Failed to generate Super ID after token refresh: {str(retry_err)}"
                    )
                    raise HTTPException(
                        status_code=503,
                        detail=f"Super ID service unavailable: {str(retry_err)}",
                    )
            raise HTTPException(
                status_code=503,
                detail=f"Super ID service unavailable: {str(e)}",
            )

    async def get_super_id_info(self, super_id: uuid.UUID) -> Dict:
        """
        Get information about an existing Super ID.

        Args:
            super_id: The UUID to look up

        Returns:
            Dict: Information about the Super ID

        Raises:
            HTTPException: If Super ID lookup fails
        """
        try:
            # Get auth headers with a valid token
            headers = await auth_service_client.get_auth_header()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/super_ids/{super_id}",
                    headers=headers,
                    timeout=10.0,
                )

                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to get Super ID info: {str(e)}")
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 401:
                # If unauthorized, try with a fresh token
                try:
                    headers = await auth_service_client.get_auth_header(
                        force_refresh=True
                    )
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            f"{self.base_url}/super_ids/{super_id}",
                            headers=headers,
                            timeout=10.0,
                        )

                        response.raise_for_status()
                        return response.json()
                except httpx.HTTPError as retry_err:
                    logger.error(
                        f"Failed to get Super ID info after token refresh: {str(retry_err)}"
                    )
                    raise HTTPException(
                        status_code=503,
                        detail=f"Super ID service unavailable: {str(retry_err)}",
                    )
            raise HTTPException(
                status_code=503,
                detail=f"Super ID service unavailable: {str(e)}",
            )


# Create a global instance of the super ID service client
super_id_service_client = SuperIdServiceClient()
