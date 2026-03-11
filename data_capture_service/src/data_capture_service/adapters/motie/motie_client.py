"""
HTTP client for the Motie AI scraping API.

Endpoints:
- POST /api/v1/agent/invoke  — Start a new scraping session
- GET  /api/v1/agent/session/:id — Check session status / get results
- GET  /api/v1/projects/search — Search for existing projects by URL
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from data_capture_service.config import settings

logger = logging.getLogger(__name__)


@dataclass
class MotieInvokeResponse:
    """Response from POST /api/v1/agent/invoke."""

    session_id: str
    status: str
    message: Optional[str] = None


@dataclass
class MotieSessionResponse:
    """Response from GET /api/v1/agent/session/:id."""

    session_id: str
    status: str  # "running", "completed", "failed"
    results_file_url: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class MotieProjectMatch:
    """A matching project from GET /api/v1/projects/search."""

    project_id: str
    url: str
    name: Optional[str] = None
    results_file_url: Optional[str] = None
    created_at: Optional[str] = None


class MotieClient:
    """
    HTTP client for the Motie API.

    Handles authentication, request building, and response parsing.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_token: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.base_url = (base_url or settings.MOTIE_BASE_URL).rstrip("/")
        self.api_token = api_token or settings.MOTIE_API_TOKEN
        self.timeout = timeout

    def _get_headers(self) -> Dict[str, str]:
        """Build auth headers for Motie API requests."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    async def invoke(
        self,
        url: str,
        prompt: Optional[str] = None,
    ) -> MotieInvokeResponse:
        """
        Start a new Motie scraping session.

        POST /api/v1/agent/invoke
        """
        payload: Dict[str, Any] = {"url": url}
        if prompt:
            payload["prompt"] = prompt

        logger.info(f"Invoking Motie agent for URL: {url}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/agent/invoke",
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        session_id = data.get("sessionId") or data.get("session_id", "")
        status = data.get("status", "unknown")

        logger.info(f"Motie invoke response: session_id={session_id}, status={status}")

        return MotieInvokeResponse(
            session_id=session_id,
            status=status,
            message=data.get("message"),
        )

    async def get_session(self, session_id: str) -> MotieSessionResponse:
        """
        Check the status of a Motie session.

        GET /api/v1/agent/session/:id
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/agent/session/{session_id}",
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        return MotieSessionResponse(
            session_id=session_id,
            status=data.get("status", "unknown"),
            results_file_url=data.get("resultsFileUrl") or data.get("results_file_url"),
            error=data.get("error"),
            metadata=data.get("metadata"),
        )

    async def search_projects(self, url: str) -> List[MotieProjectMatch]:
        """
        Search for existing Motie projects that have data_captured this URL.

        GET /api/v1/projects/search?url=...
        """
        logger.info(f"Searching Motie projects for URL: {url}")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/projects/search",
                params={"url": url},
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        projects = data if isinstance(data, list) else data.get("projects", [])

        matches = []
        for proj in projects:
            matches.append(
                MotieProjectMatch(
                    project_id=proj.get("projectId") or proj.get("project_id", ""),
                    url=proj.get("url", ""),
                    name=proj.get("name"),
                    results_file_url=proj.get("resultsFileUrl")
                    or proj.get("results_file_url"),
                    created_at=proj.get("createdAt") or proj.get("created_at"),
                )
            )

        logger.info(f"Found {len(matches)} existing Motie projects for {url}")
        return matches

    async def download_results(self, results_file_url: str) -> Dict[str, Any]:
        """
        Download results from a pre-signed S3 URL.

        GET <pre-signed S3 URL>
        """
        logger.info(f"Downloading Motie results from: {results_file_url[:80]}...")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                results_file_url,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()


# Global instance
motie_client = MotieClient()
