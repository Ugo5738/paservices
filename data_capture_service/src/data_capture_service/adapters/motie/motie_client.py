"""
HTTP client for the Motie v2 API.

Endpoints:
- POST /api/v1/projects                     — Create a project
- GET  /api/v1/projects                     — List projects
- GET  /api/v1/projects/:id                 — Get project details
- POST /api/v1/projects/:id/agent/invoke    — Start an agent session
- GET  /api/v1/agent/session/:id            — Poll session status
- POST /api/v1/projects/:id/deploy          — Deploy project
- GET  /api/v1/agent/deployment/:id         — Poll deployment status
- GET  {api_url}/openapi.json               — Discover deployed routes
- GET  {api_url}{route_path}?listing_url=   — Call deployed scraper
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from data_capture_service.config import settings

logger = logging.getLogger(__name__)


@dataclass
class MotieInvokeResponse:
    """Response from POST /api/v1/projects/:id/agent/invoke."""

    session_id: str
    status: str
    message: Optional[str] = None


@dataclass
class MotieSessionResponse:
    """Response from GET /api/v1/agent/session/:id."""

    session_id: str
    status: str  # "running", "completed", "failed"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class MotieProjectResponse:
    """Response from project endpoints."""

    id: str
    name: str
    description: Optional[str] = None
    api_url: Optional[str] = None
    is_public: bool = False
    agent_status: Optional[str] = None  # idle, session_active, deploying
    active_session_id: Optional[str] = None
    last_deployment_id: Optional[str] = None
    agent_error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class MotieDeploymentResponse:
    """Response from deployment endpoints."""

    deployment_id: str
    project_id: str
    session_id: Optional[str] = None
    status: str = "pending"  # pending, deploying, deployed, failed
    is_public: bool = False
    api_url: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class MotieClient:
    """
    HTTP client for the Motie v2 API.

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

    def _get_auth_headers(self) -> Dict[str, str]:
        """Build auth-only headers (for deployed endpoint calls)."""
        headers = {"Accept": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    # ---- Project Management ----

    async def create_project(
        self, name: str, description: Optional[str] = None
    ) -> MotieProjectResponse:
        """
        Create a new Motie project.

        POST /api/v1/projects
        """
        payload: Dict[str, Any] = {"name": name}
        if description:
            payload["description"] = description

        logger.info(f"Creating Motie project: {name}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/projects",
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        project = MotieProjectResponse(
            id=data["id"],
            name=data.get("name", name),
            description=data.get("description"),
            api_url=data.get("api_url"),
            created_at=data.get("created_at"),
        )
        logger.info(f"Created Motie project: id={project.id}, name={project.name}")
        return project

    async def get_project(self, project_id: str) -> MotieProjectResponse:
        """
        Get project details including agent status.

        GET /api/v1/projects/:projectId
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/projects/{project_id}",
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        return MotieProjectResponse(
            id=data["id"],
            name=data.get("name", ""),
            description=data.get("description"),
            api_url=data.get("api_url"),
            is_public=data.get("is_public", False),
            agent_status=data.get("agent_status"),
            active_session_id=data.get("active_session_id"),
            last_deployment_id=data.get("last_deployment_id"),
            agent_error=data.get("agent_error"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    async def list_projects(self) -> List[MotieProjectResponse]:
        """
        List all projects.

        GET /api/v1/projects
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/projects",
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        projects = []
        for p in data if isinstance(data, list) else []:
            projects.append(
                MotieProjectResponse(
                    id=p["id"],
                    name=p.get("name", ""),
                    description=p.get("description"),
                    api_url=p.get("api_url"),
                    is_public=p.get("is_public", False),
                    created_at=p.get("created_at"),
                    updated_at=p.get("updated_at"),
                )
            )
        return projects

    # ---- Agent Sessions ----

    async def invoke(self, project_id: str, prompt: str) -> MotieInvokeResponse:
        """
        Start an agent session on a project.

        POST /api/v1/projects/:projectId/agent/invoke

        The prompt should describe the scraper to build, including
        the target URL and the data fields to extract.
        """
        payload: Dict[str, Any] = {"prompt": prompt}

        logger.info(f"Invoking Motie agent on project {project_id}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/projects/{project_id}/agent/invoke",
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        session_id = data.get("session_id") or data.get("sessionId", "")
        status = data.get("status", "unknown")

        logger.info(f"Motie agent invoked: session_id={session_id}, status={status}")

        return MotieInvokeResponse(
            session_id=session_id,
            status=status,
            message=data.get("message"),
        )

    async def get_session(self, session_id: str) -> MotieSessionResponse:
        """
        Check the status of a Motie session.

        GET /api/v1/agent/session/:sessionId
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
            session_id=data.get("session_id", session_id),
            status=data.get("status", "unknown"),
            result=data.get("result"),
            error=data.get("error"),
            created_at=data.get("created_at"),
            completed_at=data.get("completed_at"),
        )

    # ---- Deployments ----

    async def deploy(self, project_id: str) -> MotieDeploymentResponse:
        """
        Deploy a project's latest code to a live endpoint.

        POST /api/v1/projects/:projectId/deploy
        """
        logger.info(f"Deploying Motie project {project_id}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/projects/{project_id}/deploy",
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        deployment = MotieDeploymentResponse(
            deployment_id=data.get("deployment_id", ""),
            project_id=data.get("project_id", project_id),
            session_id=data.get("session_id"),
            status=data.get("status", "pending"),
            api_url=data.get("api_url"),
        )
        logger.info(
            f"Motie deployment started: deployment_id={deployment.deployment_id}"
        )
        return deployment

    async def get_deployment(self, deployment_id: str) -> MotieDeploymentResponse:
        """
        Poll deployment status.

        GET /api/v1/agent/deployment/:deploymentId
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/agent/deployment/{deployment_id}",
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        return MotieDeploymentResponse(
            deployment_id=data.get("deployment_id", deployment_id),
            project_id=data.get("project_id", ""),
            session_id=data.get("session_id"),
            status=data.get("status", "unknown"),
            is_public=data.get("is_public", False),
            api_url=data.get("api_url"),
            error=data.get("error"),
            created_at=data.get("created_at"),
            completed_at=data.get("completed_at"),
        )

    # ---- Deployed Endpoint Calls ----

    async def get_openapi_spec(self, api_url: str) -> Dict[str, Any]:
        """
        Fetch the OpenAPI spec from a deployed endpoint to discover routes.

        GET {api_url}/openapi.json
        """
        url = f"{api_url.rstrip('/')}/openapi.json"
        logger.info(f"Fetching OpenAPI spec from {url}")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self._get_auth_headers(),
                timeout=settings.MOTIE_DEPLOYED_ENDPOINT_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()

    async def call_deployed_endpoint(
        self,
        api_url: str,
        route_path: str,
        listing_url: str,
    ) -> Dict[str, Any]:
        """
        Call a deployed Motie scraper endpoint with a listing URL.

        GET {api_url}{route_path}?listing_url={listing_url}
        """
        url = f"{api_url.rstrip('/')}{route_path}"
        logger.info(
            f"Calling deployed Motie endpoint: {url} with listing_url={listing_url}"
        )

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params={"listing_url": listing_url},
                headers=self._get_auth_headers(),
                timeout=settings.MOTIE_DEPLOYED_ENDPOINT_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()


# Global instance
motie_client = MotieClient()
