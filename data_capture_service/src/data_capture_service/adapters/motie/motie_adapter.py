"""
Motie Adapter — implements the DataCaptureAdapter protocol.

Supports the full Motie v2 flow taxonomy:

- Flow D (routing): Check internal registry → known domain? → Flow B, else → Flow A.
- Flow B (deployed endpoint): Call existing deployed scraper directly (fast, cheap).
- Flow A (agent build): Create project, invoke agent, deploy, discover route, call.
- Flow E (repair/rebuild): When Flow B fails on a known domain, invoke a new agent
  session on the *same* project with a repair prompt, redeploy, call updated endpoint.
- Flow G (validation/drift): Handled by the pipeline's baseline/scoring layer.
- Flow F (multiple scrapers per website): Deferred — future enhancement.
"""

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.adapters.base import (
    AdapterStatus,
    CompletenessScore,
    DataCaptureRequest,
    ParsedDataCaptureResult,
    RawDataCaptureResult,
)
from data_capture_service.config import settings
from data_capture_service.crud import motie_project_crud
from data_capture_service.db import AsyncSessionLocal
from data_capture_service.services.field_registry import (
    compute_completeness_score,
    compute_field_presence,
)

from .motie_client import MotieClient, motie_client
from .motie_parser import parse_motie_result
from .motie_poller import (
    MotiePollerError,
    MotiePollerTimeout,
    poll_deployment,
    poll_session,
)

logger = logging.getLogger(__name__)

# Default prompt for Motie agent invocation.
# Instructs the agent to build a FastAPI endpoint that accepts listing_url
# and extracts all property details.
DEFAULT_MOTIE_PROMPT = (
    "Build a scraper for this property listing website. "
    "The scraper should accept a listing_url query parameter and extract "
    "all property details from the page at that URL.\n\n"
    "Extract these fields and return them as a JSON object. "
    "If a detail isn't present on the page, put null as the value:\n\n"
    "Address (Road name), Floorplan(s) Images URL(s), Image(s) URL(s) (ALL, High Res), "
    "Source URL, Price, Address (Town), Bedrooms (number), Estate Agent Name, "
    "Estate Agent Address, Transaction Type Details, Bathrooms (number), "
    "Type (House, Detached etc), Created (came to market), Address (full), "
    "Address (Postcode), Description (Full), Rightmove URL, Description (Short), "
    "Size, Tenure, Garden, Parking, Address (Location Coordinates), "
    "Status/Availability, Last Update & Reason, EPC(s), Train Station (nearby), "
    "Video(s) URLs, Access, Accessibility, Flood Risk, Heating, Listed?, "
    "Restrictions, Shared Ownership, Utilities"
)

# Reverse mapping: canonical field name → Motie prompt descriptor
# Used to build targeted retry prompts for specific missing fields
CANONICAL_TO_PROMPT_KEY: Dict[str, str] = {
    "address_road": "Address (Road name)",
    "floorplan_urls": "Floorplan(s) Images URL(s)",
    "image_urls": "Image(s) URL(s) (ALL, High Res)",
    "source_url": "Source URL",
    "price": "Price",
    "address_town": "Address (Town)",
    "bedrooms": "Bedrooms (number)",
    "estate_agent_name": "Estate Agent Name",
    "agent_address": "Estate Agent Address",
    "transaction_type": "Transaction Type Details",
    "bathrooms": "Bathrooms (number)",
    "property_type": "Type (House, Detached etc)",
    "created_date": "Created (came to market)",
    "full_address": "Address (full)",
    "postcode": "Address (Postcode)",
    "description": "Description (Full)",
    "rightmove_url": "Rightmove URL",
    "description_short": "Description (Short)",
    "size": "Size",
    "tenure": "Tenure",
    "garden": "Garden",
    "parking": "Parking",
    "address_coordinates": "Address (Location Coordinates)",
    "status_availability": "Status/Availability",
    "last_update_reason": "Last Update & Reason",
    "epcs": "EPC(s)",
    "train_station_nearby": "Train Station (nearby)",
    "video_urls": "Video(s) URLs",
    "access": "Access",
    "accessibility": "Accessibility",
    "flood_risk": "Flood Risk",
    "heating": "Heating",
    "listed": "Listed?",
    "restrictions": "Restrictions",
    "shared_ownership": "Shared Ownership",
    "utilities": "Utilities",
}

# Default route path for deployed Motie scrapers.
# Used as fallback when OpenAPI spec discovery fails.
DEFAULT_ROUTE_PATH = "/v1/listing-extract"


def _extract_domain(url: str) -> str:
    """Extract the domain (host) from a URL, stripping www. prefix."""
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path.split("/")[0]
    if domain.startswith("www."):
        domain = domain[4:]
    return domain.lower()


def _discover_route_from_openapi(spec: Dict[str, Any]) -> Optional[str]:
    """
    Extract the first GET route path from an OpenAPI spec.

    Motie-deployed scrapers typically expose a single GET endpoint
    that accepts a listing_url query parameter.
    """
    paths = spec.get("paths", {})
    for path, methods in paths.items():
        if isinstance(methods, dict) and "get" in methods:
            return path
    return None


class MotieAdapter:
    """
    DataCapture adapter for Motie AI (v2 API).

    Implements the DataCaptureAdapter protocol with the full flow taxonomy:

    Flow D (routing decision — the main fetch_raw logic):
    ├── Known domain with deployed endpoint? → Flow B (direct call)
    │   └── Flow B fails? → Flow E (repair/rebuild on same project)
    └── Unknown domain? → Flow A (full build cycle)

    Flow G (validation & drift monitoring) is handled by the pipeline layer.
    Flow F (multiple scrapers per website) is deferred for future implementation.
    """

    name: str = "motie"
    supported_domains: List[str] = ["*"]  # Motie can scrape any domain

    def __init__(self, client: Optional[MotieClient] = None):
        self.client = client or motie_client

    # --- DB helpers: use short-lived sessions to avoid stale connections ---

    async def _db_get_project(self, domain: str):
        """Look up a MotieScraperProject by domain using a fresh session."""
        try:
            async with AsyncSessionLocal() as db:
                return await motie_project_crud.get_by_domain(db, domain)
        except Exception as e:
            logger.warning(f"Failed to look up Motie project for {domain}: {e}")
            return None

    async def _db_create_project(self, domain: str, motie_project_id: str, name: str):
        """Create a MotieScraperProject using a fresh session."""
        try:
            async with AsyncSessionLocal() as db:
                try:
                    project = await motie_project_crud.create(
                        db=db,
                        domain=domain,
                        motie_project_id=motie_project_id,
                        motie_project_name=name,
                    )
                    await db.commit()
                    return project
                except IntegrityError:
                    await db.rollback()
                    project = await motie_project_crud.get_by_domain(db, domain)
                    if project:
                        logger.info(
                            f"Concurrent create detected, reusing project "
                            f"{project.motie_project_id} for {domain}"
                        )
                    return project
        except Exception as e:
            logger.warning(f"Failed to store Motie project for {domain}: {e}")
            return None

    async def _db_update_deployment(self, project, **kwargs):
        """Update deployment info on a MotieScraperProject using a fresh session."""
        if not project:
            return
        try:
            async with AsyncSessionLocal() as db:
                await motie_project_crud.update_deployment(
                    db=db, project_id=project.id, **kwargs
                )
                await db.commit()
        except Exception as e:
            logger.warning(f"Failed to update deployment for project {project.id}: {e}")

    def build_retry_prompt(
        self,
        missing_fields: List[str],
        baseline: Optional[Any] = None,
    ) -> Optional[str]:
        """
        Build a targeted Motie prompt focusing on specific missing fields.

        If a Firecrawl baseline is provided, references the specific fields
        that the baseline detected as present on the page but the scraper
        failed to extract — giving the agent concrete evidence of what to fix.

        Returns None if no valid prompt keys can be mapped from the missing fields.
        """
        prompt_keys = []
        for field in missing_fields:
            key = CANONICAL_TO_PROMPT_KEY.get(field)
            if key:
                prompt_keys.append(key)

        if not prompt_keys:
            return None

        # Build baseline comparison info if available
        baseline_info = ""
        if baseline and hasattr(baseline, "field_presence") and baseline.field_presence:
            baseline_present = [
                f for f, present in baseline.field_presence.items() if present
            ]
            baseline_missing_from_scraper = [
                f for f in baseline_present if f in missing_fields
            ]
            if baseline_missing_from_scraper:
                baseline_info = (
                    "\n\nIMPORTANT: Our validation system independently confirmed "
                    "these fields ARE present on the page but your code failed to "
                    f"extract them: {baseline_missing_from_scraper}. "
                    f"The page definitely contains: {baseline_present}. "
                    "Fix your extraction code to capture these fields."
                )

        return (
            "From this property page, I need you to carefully look for these specific "
            "details that were not found in the previous extraction. "
            "Look thoroughly in ALL sections of the page including sidebars, headers, "
            "footers, meta tags, breadcrumbs, and any tabbed or hidden content sections. "
            "Return an object with these keys and extracted values. "
            "If a detail truly isn't present on the page, put null as the value:\n\n"
            + ", ".join(prompt_keys)
            + baseline_info
        )

    async def fetch_raw(self, request: DataCaptureRequest) -> RawDataCaptureResult:
        """
        Fetch raw data using Motie — implements Flow D (routing).

        Routing logic:
        1. Extract domain from URL
        2. Look up MotieScraperProject by domain in DB
        3. If project exists with deployed endpoint → Flow B (call deployed endpoint)
           a. If Flow B fails → Flow E (repair scraper on same project, redeploy)
        4. If project exists but no deployment → Flow A (invoke agent, deploy, call)
        5. If no project exists → Flow A (create project, invoke agent, deploy, call)

        For retry attempts with custom prompts, always goes through the
        rebuild cycle (new session on existing project → redeploy → call).
        """
        start_time = time.time()
        domain = _extract_domain(request.url)

        # Use fresh DB sessions for each DB operation to avoid stale
        # connections during long-running Motie polls.  The pipeline's
        # session may be idle for 30+ minutes, which PgBouncer/Supabase
        # will kill.
        db: Optional[AsyncSession] = None  # kept for signature compat; unused

        # --- Retry with custom prompt: invoke new session on existing project ---
        if request.prompt:
            return await self._handle_retry(request, db, domain, start_time)

        # --- Look up existing project (Flow D routing) ---
        project = await self._db_get_project(domain)

        # --- Flow B: Call deployed endpoint (known domain) ---
        if (
            project
            and project.api_url
            and project.route_path
            and project.is_active
            and project.deployment_status == "deployed"
        ):
            try:
                result = await self._flow_b_deployed(
                    request.url, project.api_url, project.route_path, start_time
                )
                if result.status == AdapterStatus.SUCCESS:
                    return result

                # Flow B failed → escalate to Flow E (repair/rebuild)
                flow_b_error = result.error_message or "Unknown error"
                logger.warning(
                    f"Flow B failed for {domain}: {flow_b_error}. "
                    f"Escalating to Flow E (repair/rebuild)."
                )
            except Exception as e:
                flow_b_error = str(e)
                logger.warning(
                    f"Flow B failed for {domain}: {e}. "
                    f"Escalating to Flow E (repair/rebuild)."
                )

            # --- Flow E: Repair/rebuild on existing project ---
            try:
                return await self._flow_e_repair(
                    request, db, domain, project, flow_b_error, start_time
                )
            except (MotiePollerTimeout, MotiePollerError, Exception) as e:
                duration_ms = int((time.time() - start_time) * 1000)
                status = (
                    AdapterStatus.TIMEOUT
                    if isinstance(e, MotiePollerTimeout)
                    else AdapterStatus.FAILED
                )
                logger.error(
                    f"Flow E (repair) also failed for {domain}: {e}. "
                    f"Domain may need manual attention."
                )
                return RawDataCaptureResult(
                    adapter_name=self.name,
                    url=request.url,
                    status=status,
                    error_message=f"Flow B failed ({flow_b_error}), Flow E repair also failed: {e}",
                    duration_ms=duration_ms,
                )

        # --- Flow A: Build, deploy, call (unknown domain or undeployed project) ---
        try:
            return await self._flow_a_build(request, db, domain, project, start_time)
        except MotiePollerTimeout as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return RawDataCaptureResult(
                adapter_name=self.name,
                url=request.url,
                status=AdapterStatus.TIMEOUT,
                error_message=str(e),
                duration_ms=duration_ms,
            )
        except MotiePollerError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return RawDataCaptureResult(
                adapter_name=self.name,
                url=request.url,
                status=AdapterStatus.FAILED,
                error_message=str(e),
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Motie adapter fetch_raw failed: {e}", exc_info=True)
            return RawDataCaptureResult(
                adapter_name=self.name,
                url=request.url,
                status=AdapterStatus.FAILED,
                error_message=str(e),
                duration_ms=duration_ms,
            )

    # ──────────────────────────────────────────────────────────────────────
    # Flow B — Call existing deployed endpoint
    # ──────────────────────────────────────────────────────────────────────

    async def _flow_b_deployed(
        self,
        listing_url: str,
        api_url: str,
        route_path: str,
        start_time: float,
    ) -> RawDataCaptureResult:
        """
        Flow B: Call an existing deployed Motie scraper endpoint.

        GET {api_url}{route_path}?listing_url={listing_url}

        Fast, cheap, deterministic. No agent involvement.
        """
        logger.info(
            f"Flow B: calling deployed endpoint {api_url}{route_path} "
            f"for {listing_url}"
        )

        data = await self.client.call_deployed_endpoint(
            api_url=api_url,
            route_path=route_path,
            listing_url=listing_url,
        )

        content_hash = hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Flow B: got response in {duration_ms}ms")

        return RawDataCaptureResult(
            adapter_name=f"{self.name}_deployed",
            url=listing_url,
            status=AdapterStatus.SUCCESS,
            payload=data,
            content_hash=content_hash,
            duration_ms=duration_ms,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Flow A — Full build cycle for unknown domains
    # ──────────────────────────────────────────────────────────────────────

    async def _flow_a_build(
        self,
        request: DataCaptureRequest,
        db: Optional[AsyncSession],
        domain: str,
        project,  # Optional[MotieScraperProject]
        start_time: float,
    ) -> RawDataCaptureResult:
        """
        Flow A: Full build cycle — create project, invoke agent, deploy, call endpoint.

        Used for first-time builds on unknown domains (no existing project)
        or domains with a project but no successful deployment.

        Steps:
        1. Create Motie project (if none exists)
        2. Invoke agent session with prompt (including target URL)
        3. Poll session until complete
        4. Deploy the project
        5. Poll deployment until deployed
        6. Discover route via OpenAPI spec
        7. Update DB with api_url and route_path
        8. Call the deployed endpoint
        """
        logger.info(f"Flow A: building new scraper for domain {domain}")

        # Step 1: Create or reuse project
        motie_project_id = None
        if project:
            motie_project_id = project.motie_project_id
            logger.info(
                f"Reusing existing Motie project {motie_project_id} for {domain}"
            )
        else:
            project_name = f"data-capture-{domain}"
            create_resp = await self.client.create_project(
                name=project_name,
                description=f"Property data capture scraper for {domain}",
            )
            motie_project_id = create_resp.id
            logger.info(f"Created Motie project {motie_project_id} for {domain}")

            # Store in DB
            project = await self._db_create_project(
                domain, motie_project_id, project_name
            )
            if project:
                motie_project_id = project.motie_project_id

        # Steps 2–8: Invoke, deploy, discover, call
        return await self._invoke_deploy_call(
            request=request,
            db=db,
            project=project,
            motie_project_id=motie_project_id,
            prompt=f"Target URL: {request.url}\n\n{DEFAULT_MOTIE_PROMPT}",
            start_time=start_time,
            flow_label="Flow A",
        )

    # ──────────────────────────────────────────────────────────────────────
    # Flow E — Repair/rebuild a broken scraper
    # ──────────────────────────────────────────────────────────────────────

    async def _flow_e_repair(
        self,
        request: DataCaptureRequest,
        db: Optional[AsyncSession],
        domain: str,
        project,  # MotieScraperProject (must exist for Flow E)
        flow_b_error: str,
        start_time: float,
    ) -> RawDataCaptureResult:
        """
        Flow E: Repair/rebuild a broken deployed scraper.

        When Flow B fails (endpoint errors, bad data, HTTP errors), we invoke
        a new agent session on the *same* project with a repair prompt that
        includes:
        - The failing URL
        - The error details from Flow B
        - Instructions to fix the scraper

        The agent sees the existing scraper code in the project and can fix it.
        After the session completes, we redeploy and call the updated endpoint.
        """
        logger.info(
            f"Flow E: repairing scraper for {domain} "
            f"(project={project.motie_project_id}, error={flow_b_error})"
        )

        # Mark deployment as needing repair in DB
        await self._db_update_deployment(project, deployment_status="repairing")

        # Build repair prompt — give the agent context about what went wrong
        repair_prompt = (
            f"The deployed scraper for this website has broken or is returning errors.\n\n"
            f"Failing URL: {request.url}\n"
            f"Error: {flow_b_error}\n\n"
            f"Please fix the scraper so it correctly handles this URL. "
            f"The scraper should accept a listing_url query parameter and extract "
            f"all property details from the page at that URL.\n\n"
            f"Extract these fields and return them as a JSON object. "
            f"If a detail isn't present on the page, put null as the value:\n\n"
            f"Address (Road name), Floorplan(s) Images URL(s), "
            f"Image(s) URL(s) (ALL, High Res), Source URL, Price, Address (Town), "
            f"Bedrooms (number), Estate Agent Name, Estate Agent Address, "
            f"Transaction Type Details, Bathrooms (number), "
            f"Type (House, Detached etc), Created (came to market), Address (full), "
            f"Address (Postcode), Description (Full), Rightmove URL, "
            f"Description (Short), Size, Tenure, Garden, Parking, "
            f"Address (Location Coordinates), Status/Availability, "
            f"Last Update & Reason, EPC(s), Train Station (nearby), "
            f"Video(s) URLs, Access, Accessibility, Flood Risk, Heating, Listed?, "
            f"Restrictions, Shared Ownership, Utilities"
        )

        return await self._invoke_deploy_call(
            request=request,
            db=db,
            project=project,
            motie_project_id=project.motie_project_id,
            prompt=repair_prompt,
            start_time=start_time,
            flow_label="Flow E",
        )

    # ──────────────────────────────────────────────────────────────────────
    # Shared: invoke session → deploy → discover route → call endpoint
    # ──────────────────────────────────────────────────────────────────────

    async def _invoke_deploy_call(
        self,
        request: DataCaptureRequest,
        db: Optional[AsyncSession],
        project,  # Optional[MotieScraperProject]
        motie_project_id: str,
        prompt: str,
        start_time: float,
        flow_label: str = "Flow",
    ) -> RawDataCaptureResult:
        """
        Shared logic for Flow A, Flow E, and retries:
        invoke agent session → poll → deploy → poll → discover route → call endpoint.
        """
        # Step 1: Invoke agent session
        invoke_resp = await self.client.invoke(
            project_id=motie_project_id,
            prompt=prompt,
        )
        session_id = invoke_resp.session_id
        logger.info(f"{flow_label}: agent session started: {session_id}")

        # Step 2: Poll session until complete
        await poll_session(self.client, session_id)
        logger.info(f"{flow_label}: agent session completed: {session_id}")

        # Update DB with session ID
        await self._db_update_deployment(project, last_session_id=session_id)

        # Step 3: Deploy the project
        deploy_resp = await self.client.deploy(motie_project_id)
        deployment_id = deploy_resp.deployment_id
        logger.info(f"{flow_label}: deployment started: {deployment_id}")

        await self._db_update_deployment(
            project, deployment_id=deployment_id, deployment_status="deploying"
        )

        # Step 4: Poll deployment until deployed
        deployment = await poll_deployment(self.client, deployment_id)
        api_url = deployment.api_url
        logger.info(f"{flow_label}: deployment complete, api_url={api_url}")

        if not api_url:
            duration_ms = int((time.time() - start_time) * 1000)
            return RawDataCaptureResult(
                adapter_name=f"{self.name}_build",
                url=request.url,
                status=AdapterStatus.FAILED,
                error_message=f"{flow_label}: deployment completed but no api_url returned",
                duration_ms=duration_ms,
            )

        # Step 5: Discover route via OpenAPI spec
        route_path = DEFAULT_ROUTE_PATH
        try:
            spec = await self.client.get_openapi_spec(api_url)
            discovered = _discover_route_from_openapi(spec)
            if discovered:
                route_path = discovered
                logger.info(
                    f"{flow_label}: discovered route from OpenAPI: {route_path}"
                )
            else:
                logger.info(
                    f"{flow_label}: no GET route in OpenAPI spec, "
                    f"using default: {route_path}"
                )
        except Exception as e:
            logger.warning(
                f"{flow_label}: OpenAPI spec discovery failed, "
                f"using default route: {e}"
            )

        # Step 6: Update DB with deployment info
        await self._db_update_deployment(
            project,
            api_url=api_url,
            route_path=route_path,
            deployment_id=deployment_id,
            deployment_status="deployed",
        )

        # Step 7: Call the deployed endpoint
        data = await self.client.call_deployed_endpoint(
            api_url=api_url,
            route_path=route_path,
            listing_url=request.url,
        )

        content_hash = hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"{flow_label}: complete in {duration_ms}ms for {_extract_domain(request.url)}"
        )

        return RawDataCaptureResult(
            adapter_name=f"{self.name}_build",
            url=request.url,
            status=AdapterStatus.SUCCESS,
            payload=data,
            content_hash=content_hash,
            provider_run_id=session_id,
            duration_ms=duration_ms,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Retry handler (pipeline auto-retry for missing fields)
    # ──────────────────────────────────────────────────────────────────────

    async def _handle_retry(
        self,
        request: DataCaptureRequest,
        db: Optional[AsyncSession],
        domain: str,
        start_time: float,
    ) -> RawDataCaptureResult:
        """
        Handle pipeline auto-retry with custom prompt for missing fields.

        Invokes a new session on the existing project with the retry prompt,
        then redeploys and calls the endpoint. Uses the shared
        _invoke_deploy_call path.
        """
        logger.info(f"Retry: invoking new session for {domain} with custom prompt")

        # Find existing project
        project = await self._db_get_project(domain)
        motie_project_id = None

        if project:
            motie_project_id = project.motie_project_id
        else:
            # Create project for retry (shouldn't normally happen)
            project_name = f"data-capture-{domain}"
            create_resp = await self.client.create_project(
                name=project_name,
                description=f"Property data capture scraper for {domain}",
            )
            motie_project_id = create_resp.id

        # Build prompt with URL + custom retry prompt
        prompt = f"Target URL: {request.url}\n\n{request.prompt}"

        try:
            return await self._invoke_deploy_call(
                request=request,
                db=db,
                project=project,
                motie_project_id=motie_project_id,
                prompt=prompt,
                start_time=start_time,
                flow_label="Retry",
            )
        except MotiePollerTimeout as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return RawDataCaptureResult(
                adapter_name=self.name,
                url=request.url,
                status=AdapterStatus.TIMEOUT,
                error_message=str(e),
                duration_ms=duration_ms,
            )
        except (MotiePollerError, Exception) as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Motie retry failed: {e}", exc_info=True)
            return RawDataCaptureResult(
                adapter_name=self.name,
                url=request.url,
                status=AdapterStatus.FAILED,
                error_message=str(e),
                duration_ms=duration_ms,
            )

    # ──────────────────────────────────────────────────────────────────────
    # Parse & Score
    # ──────────────────────────────────────────────────────────────────────

    async def parse(self, raw: RawDataCaptureResult) -> ParsedDataCaptureResult:
        """Parse Motie raw result into structured fields."""
        if raw.status != AdapterStatus.SUCCESS or not raw.payload:
            return ParsedDataCaptureResult(
                adapter_name=self.name,
                url=raw.url,
                status=AdapterStatus.FAILED,
                error_message=raw.error_message or "No data to parse",
            )

        try:
            fields, image_urls, floorplan_urls = parse_motie_result(
                raw.payload, raw.url
            )

            field_presence = compute_field_presence(fields)
            missing = [f for f, present in field_presence.items() if not present]

            return ParsedDataCaptureResult(
                adapter_name=self.name,
                url=raw.url,
                status=AdapterStatus.SUCCESS,
                fields=fields,
                field_presence=field_presence,
                image_urls=image_urls,
                floorplan_urls=floorplan_urls,
                missing_fields=missing,
            )

        except Exception as e:
            logger.error(f"Motie parse failed: {e}", exc_info=True)
            return ParsedDataCaptureResult(
                adapter_name=self.name,
                url=raw.url,
                status=AdapterStatus.FAILED,
                error_message=str(e),
            )

    async def score(self, parsed: ParsedDataCaptureResult) -> CompletenessScore:
        """Compute completeness score for parsed Motie result."""
        if parsed.status != AdapterStatus.SUCCESS:
            return CompletenessScore(overall=0.0)

        return compute_completeness_score(parsed.field_presence)


# Global instance
motie_adapter = MotieAdapter()
