"""
Super ID Service Client for generating and retrieving tracking UUIDs.
"""

import logging
import uuid
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException

from data_capture_service.clients.auth_service_client import auth_service_client
from data_capture_service.config import settings

logger = logging.getLogger(__name__)


class SuperIdServiceClient:
    """
    Client for interacting with the Super ID Service API for UUID generation and tracking.
    """

    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.SUPER_ID_SERVICE_URL
        logger.info(f"Initializing Super ID Service Client with URL: {self.base_url}")

    async def create_super_id(
        self,
        description: str = None,
        metadata: Optional[Dict[str, Any]] = None,
        source_service: str = "data_capture_service",
    ) -> uuid.UUID:
        """
        Generate a new Super ID UUID for tracking purposes.
        """
        try:
            headers = await auth_service_client.get_auth_header()

            final_metadata = {}
            if metadata:
                final_metadata = metadata
            elif description:
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

                return uuid.UUID(data["super_id"])

        except httpx.HTTPError as e:
            logger.error(f"Failed to generate Super ID: {str(e)}")
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 401:
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
        """Get information about an existing Super ID."""
        try:
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
