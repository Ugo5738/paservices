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


    async def record_activity(
        self,
        super_id: uuid.UUID,
        used_by: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Record an activity entry for a SuperID in the SuperID Metadata store.

        Non-blocking: any failure (network, auth, permission, 5xx, …) is
        logged and the method returns None. Activity records are
        observability metadata; losing one record must not break the
        operational path of the analysis.

        See docs/superid_principles.md section 5 and
        docs/superid_data_capture_design.md section 3.3.
        """
        payload: Dict[str, Any] = {
            "super_id": str(super_id),
            "used_by": used_by,
            "source": source,
        }
        if metadata is not None:
            payload["metadata"] = metadata
        try:
            headers = await auth_service_client.get_auth_header()
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/activity_records",
                    json=payload,
                    headers=headers,
                    timeout=10.0,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.warning(
                "Failed to record activity for super_id=%s used_by=%s source=%s: %s",
                super_id,
                used_by,
                source,
                e,
            )
            return None

    async def record_link(
        self,
        super_id_a: uuid.UUID,
        super_id_b: uuid.UUID,
        created_by: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Record a link entry in the SuperID Metadata store between two SuperIDs.

        Bidirectional: super_id_a / super_id_b order is not semantically
        meaningful. Non-blocking by design (see `record_activity`).
        """
        payload: Dict[str, Any] = {
            "super_id_a": str(super_id_a),
            "super_id_b": str(super_id_b),
            "created_by": created_by,
            "source": source,
        }
        if metadata is not None:
            payload["metadata"] = metadata
        try:
            headers = await auth_service_client.get_auth_header()
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/link_records",
                    json=payload,
                    headers=headers,
                    timeout=10.0,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.warning(
                "Failed to record link super_id_a=%s super_id_b=%s created_by=%s source=%s: %s",
                super_id_a,
                super_id_b,
                created_by,
                source,
                e,
            )
            return None


# Create a global instance of the super ID service client
super_id_service_client = SuperIdServiceClient()
