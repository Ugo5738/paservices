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
from urllib.parse import urlparse, urlunparse

from data_capture_service.adapters.base import (
    AdapterStatus,
    CompletenessScore,
    DataCaptureRequest,
    ParsedDataCaptureResult,
    RawDataCaptureResult,
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


def _normalize_url_for_comparison(url: str) -> str:
    """
    Normalize a URL for comparison by stripping fragments, query params,
    and trailing slashes. This ensures we match on the core property page URL.

    e.g. "https://www.rightmove.co.uk/properties/166533791#/?channel=RES_BUY"
      → "https://www.rightmove.co.uk/properties/166533791"
    """
    parsed = urlparse(url)
    # Rebuild without fragment and query string
    normalized = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip("/"),
            "",  # params
            "",  # query
            "",  # fragment
        )
    )
    return normalized.lower()


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

    def build_retry_prompt(self, missing_fields: List[str]) -> Optional[str]:
        """
        Build a targeted Motie prompt focusing on specific missing fields.

        Returns None if no valid prompt keys can be mapped from the missing fields.
        """
        prompt_keys = []
        for field in missing_fields:
            key = CANONICAL_TO_PROMPT_KEY.get(field)
            if key:
                prompt_keys.append(key)

        if not prompt_keys:
            return None

        return (
            "From this property page, I need you to carefully look for these specific "
            "details that were not found in the previous extraction. "
            "Look thoroughly in ALL sections of the page including sidebars, headers, "
            "footers, meta tags, breadcrumbs, and any tabbed or hidden content sections. "
            "Return an object with these keys and extracted values. "
            "If a detail truly isn't present on the page, put null as the value:\n\n"
            + ", ".join(prompt_keys)
        )

    async def fetch_raw(self, request: DataCaptureRequest) -> RawDataCaptureResult:
        """
        Fetch raw data using Motie.

        First tries to find existing project results (motie_existing mode).
        Falls back to invoking a new session (motie_build mode).

        If request.prompt is set (retry attempt), skips existing project search
        and invokes a fresh session with the custom prompt.
        """
        start_time = time.time()

        # Skip existing project search for retry attempts with custom prompts
        if not request.prompt:
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

    # Minimum number of non-null fields required to consider an existing session usable.
    # Sessions with fewer meaningful fields are skipped (they likely used a different
    # or too-narrow prompt and don't have enough data for our full property extraction).
    MIN_EXISTING_FIELDS = 5

    async def _try_existing(self, url: str) -> Optional[RawDataCaptureResult]:
        """
        Search for and reuse existing Motie project results.

        Validates:
        1. URL match — the session must be for the same property page
           (Motie search API may return broad/fuzzy matches from different URLs)
        2. Data quality — the session must have enough non-null fields to be useful
        """
        matches = await self.client.search_projects(url)
        if not matches:
            return None

        target_normalized = _normalize_url_for_comparison(url)
        logger.info(
            f"Checking {len(matches)} existing Motie sessions "
            f"(target URL: {target_normalized})"
        )

        # Search results only return session_id + url + prompt.
        # We need to call get_session() on each match to check if it
        # completed successfully and has a results_file URL.
        for match in matches:
            # --- URL validation ---
            # Motie's search API returns broad matches that may include
            # sessions from completely different property URLs.
            # We must verify the session URL matches our target URL.
            match_normalized = _normalize_url_for_comparison(match.url)
            if match_normalized != target_normalized:
                logger.info(
                    f"Skipping existing Motie session {match.session_id}: "
                    f"URL mismatch — session URL '{match.url}' "
                    f"does not match target '{url}'"
                )
                continue

            try:
                session = await self.client.get_session(match.session_id)
            except Exception as e:
                logger.warning(
                    f"Failed to fetch session {match.session_id} for existing project: {e}"
                )
                continue

            if session.status == "completed" and session.results_file_url:
                data = await self.client.download_results(session.results_file_url)

                # Validate data quality — skip sessions with too few meaningful fields
                raw_data = data.get("data", data) if isinstance(data, dict) else data
                if isinstance(raw_data, dict):
                    non_null_count = sum(
                        1
                        for v in raw_data.values()
                        if v is not None
                        and v != ""
                        and v != []
                        and v != "null"
                        and v != "None"
                    )
                else:
                    non_null_count = 0

                if non_null_count < self.MIN_EXISTING_FIELDS:
                    logger.info(
                        f"Skipping existing Motie session {match.session_id}: "
                        f"only {non_null_count} non-null fields "
                        f"(need >= {self.MIN_EXISTING_FIELDS})"
                    )
                    continue

                logger.info(
                    f"Reusing existing Motie session {match.session_id} for {url} "
                    f"({non_null_count} non-null fields)"
                )
                content_hash = hashlib.sha256(
                    json.dumps(data, sort_keys=True).encode()
                ).hexdigest()

                return RawDataCaptureResult(
                    adapter_name=f"{self.name}_existing",
                    url=url,
                    status=AdapterStatus.SUCCESS,
                    payload=data,
                    content_hash=content_hash,
                    provider_run_id=match.session_id,
                )

        logger.info(
            f"No existing Motie sessions with matching URL and sufficient data for {url}, "
            f"will invoke new session"
        )
        return None

    async def _invoke_and_poll(
        self, request: DataCaptureRequest, start_time: float
    ) -> RawDataCaptureResult:
        """Invoke a new Motie session, poll until complete, download results."""
        # Use custom prompt if provided (retry attempts), otherwise default
        prompt = request.prompt or DEFAULT_MOTIE_PROMPT

        # Invoke
        invoke_response = await self.client.invoke(
            url=request.url,
            prompt=prompt,
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
