"""
Motie Adapter — implements the DataCaptureAdapter protocol.

Two modes:
1. motie_existing: Search for an existing Motie project with results → reuse
2. motie_build: Invoke a new Motie agent session → poll → download → parse
"""

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional

from data_capture_service.adapters.base import (
    AdapterStatus,
    CompletenessScore,
    ParsedDataCaptureResult,
    RawDataCaptureResult,
    DataCaptureRequest,
)
from data_capture_service.config import settings
from data_capture_service.services.field_registry import (
    compute_completeness_score,
    compute_field_presence,
)

from .motie_client import MotieClient, motie_client
from .motie_parser import parse_motie_result
from .motie_poller import MotiePollerError, MotiePollerTimeout, poll_session

logger = logging.getLogger(__name__)

# Default prompt for Motie agent invocation
DEFAULT_MOTIE_PROMPT = (
    "From this property page, extract all property details. "
    "Get ALL high-resolution images if available, otherwise get the highest quality images. "
    "Return an object with these keys and extracted values. "
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


class MotieAdapter:
    """
    DataCapture adapter for Motie AI.

    Implements the DataCaptureAdapter protocol with two sub-modes:
    - motie_existing: Try to reuse results from a previously data_captured URL
    - motie_build: Invoke a new Motie session, poll until complete, download results
    """

    name: str = "motie"
    supported_domains: List[str] = ["*"]  # Motie can data_capture any domain

    def __init__(self, client: Optional[MotieClient] = None):
        self.client = client or motie_client

    async def fetch_raw(self, request: DataCaptureRequest) -> RawDataCaptureResult:
        """
        Fetch raw data using Motie.

        First tries to find existing project results (motie_existing mode).
        Falls back to invoking a new session (motie_build mode).
        """
        start_time = time.time()

        # --- Try existing project first ---
        try:
            existing_result = await self._try_existing(request.url)
            if existing_result:
                existing_result.duration_ms = int((time.time() - start_time) * 1000)
                return existing_result
        except Exception as e:
            logger.warning(f"Motie existing project search failed: {e}")

        # --- Invoke new session ---
        try:
            return await self._invoke_and_poll(request, start_time)
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

    async def _try_existing(self, url: str) -> Optional[RawDataCaptureResult]:
        """Search for and reuse existing Motie project results."""
        matches = await self.client.search_projects(url)
        if not matches:
            return None

        # Use the first match that has a results file
        for match in matches:
            if match.results_file_url:
                logger.info(
                    f"Reusing existing Motie project {match.project_id} for {url}"
                )
                data = await self.client.download_results(match.results_file_url)
                content_hash = hashlib.sha256(
                    json.dumps(data, sort_keys=True).encode()
                ).hexdigest()

                return RawDataCaptureResult(
                    adapter_name=f"{self.name}_existing",
                    url=url,
                    status=AdapterStatus.SUCCESS,
                    payload=data,
                    content_hash=content_hash,
                    provider_run_id=match.project_id,
                )

        return None

    async def _invoke_and_poll(
        self, request: DataCaptureRequest, start_time: float
    ) -> RawDataCaptureResult:
        """Invoke a new Motie session, poll until complete, download results."""
        # Invoke
        invoke_response = await self.client.invoke(
            url=request.url,
            prompt=DEFAULT_MOTIE_PROMPT,
        )

        session_id = invoke_response.session_id
        logger.info(f"Motie session started: {session_id}")

        # Poll
        session = await poll_session(self.client, session_id)

        # Download results
        if not session.results_file_url:
            return RawDataCaptureResult(
                adapter_name=f"{self.name}_build",
                url=request.url,
                status=AdapterStatus.FAILED,
                error_message="Session completed but no results file URL",
                provider_run_id=session_id,
                duration_ms=int((time.time() - start_time) * 1000),
            )

        data = await self.client.download_results(session.results_file_url)
        content_hash = hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

        return RawDataCaptureResult(
            adapter_name=f"{self.name}_build",
            url=request.url,
            status=AdapterStatus.SUCCESS,
            payload=data,
            content_hash=content_hash,
            provider_run_id=session_id,
            duration_ms=int((time.time() - start_time) * 1000),
        )

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
