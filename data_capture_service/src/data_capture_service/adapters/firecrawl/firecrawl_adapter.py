"""
Firecrawl AI Fetcher Adapter — Firecrawl /v2/agent (Spark) edition.

Uses Firecrawl's v2 Agent endpoint (Spark 1 Mini / Spark 1 Pro) for
agentic structured extraction. The agent navigates the page (handling
JS, pagination, modal dialogs, etc.) and returns structured field VALUES
against the JSON schema we provide — not just presence booleans.

History:
  v0 (FirecrawlApp.scrape_url, formats:["markdown"]) — regex over markdown
     for canonical-field PRESENCE; fields were bool|None.
  v1 (FirecrawlApp.scrape_url, formats:["json"], agent:{model:"FIRE-1"}) —
     legacy Scrape API + FIRE-1 model. FireCrawl froze this surface under
     `firecrawl.v1.*` and the FIRE-1 path now returns metadata-only on
     many portals (no structured json) — surfaced as
     "Firecrawl agent returned no structured json" with completeness ~0.06.
  v2 (THIS — Firecrawl.agent(...)) — Firecrawl's new /v2/agent endpoint
     with Spark 1. Blocking call (SDK polls internally until status
     ∈ {completed, failed, cancelled}). Returns an AgentResponse pydantic
     model whose `.data` is the structured dict matching our schema.

The completeness score reflects actual data quality (does the field have
a value?), not regex hit-rate. Same DataCaptureAdapter Protocol so the
registry/orchestrator code didn't change.
"""

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional

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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON schema describing the canonical property fields we want the agent to
# extract. Mirrors the canonical names in services.field_registry so the
# scoring step works without translation. Optional everywhere — missing
# values come back as null and the scorer treats them as absent.
# ---------------------------------------------------------------------------

PROPERTY_EXTRACTION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        # P0 — essential
        "address_road": {
            "type": ["string", "null"],
            "description": "Road / street name part of the address.",
        },
        "image_urls": {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "description": "Full list of property photo URLs at the highest resolution available.",
        },
        "floorplan_urls": {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "description": "Floorplan image URLs.",
        },
        "source_url": {
            "type": ["string", "null"],
            "description": "Canonical URL of the listing page (the page being scraped).",
        },
        "price": {
            "type": ["string", "null"],
            "description": "Asking price including currency symbol (e.g. £1,249 pcm or £550,000).",
        },
        # P1 — very high
        "address_town": {
            "type": ["string", "null"],
            "description": "Town / city of the property.",
        },
        "bedrooms": {
            "type": ["integer", "null"],
            "description": "Number of bedrooms.",
        },
        "estate_agent_name": {
            "type": ["string", "null"],
            "description": "Estate agent / lister name.",
        },
        # P2 — high
        "agent_address": {
            "type": ["string", "null"],
            "description": "Estate agent's office address.",
        },
        "transaction_type": {
            "type": ["string", "null"],
            "description": "for sale / to rent / sold / let / auction / etc.",
        },
        "bathrooms": {
            "type": ["integer", "null"],
            "description": "Number of bathrooms.",
        },
        "property_type": {
            "type": ["string", "null"],
            "description": "Detached, semi-detached, terraced, flat, bungalow, etc.",
        },
        # P3 — medium
        "created_date": {
            "type": ["string", "null"],
            "description": "When the property came to market (ISO date if possible).",
        },
        "full_address": {
            "type": ["string", "null"],
            "description": "Complete address line.",
        },
        "postcode": {
            "type": ["string", "null"],
            "description": "UK postcode.",
        },
        "description": {
            "type": ["string", "null"],
            "description": "Full property description.",
        },
        "rightmove_url": {
            "type": ["string", "null"],
            "description": "Rightmove listing URL if mentioned (cross-listing).",
        },
        # P4 — low
        "description_short": {"type": ["string", "null"]},
        "size": {"type": ["string", "null"], "description": "Floor area, e.g. '850 sq ft'."},
        "tenure": {"type": ["string", "null"]},
        "garden": {"type": ["string", "null"]},
        "parking": {"type": ["string", "null"]},
        "address_coordinates": {
            "type": ["object", "null"],
            "properties": {
                "lat": {"type": ["number", "null"]},
                "lng": {"type": ["number", "null"]},
            },
        },
        "status_availability": {"type": ["string", "null"]},
        "last_update_reason": {"type": ["string", "null"]},
        "epcs": {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "description": "EPC ratings or links to EPC documents.",
        },
        "train_station_nearby": {"type": ["string", "null"]},
        "video_urls": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
        # P5 — very low
        "access": {"type": ["string", "null"]},
        "accessibility": {"type": ["string", "null"]},
        "flood_risk": {"type": ["string", "null"]},
        "heating": {"type": ["string", "null"]},
        "listed": {"type": ["string", "null"]},
        "restrictions": {"type": ["string", "null"]},
        "shared_ownership": {"type": ["string", "null"]},
        "utilities": {"type": ["string", "null"]},
    },
}


_AGENT_PROMPT = (
    "You are extracting property listing details from a property listing "
    "page. Return data exactly matching the provided JSON schema. Use "
    "null when a field is not on the page; do not guess. For URL fields "
    "(image_urls, floorplan_urls, video_urls), return the full canonical "
    "URLs at the highest resolution you can find. For price, include the "
    "currency symbol and any qualifier like 'pcm' or 'OIRO'. Navigate "
    "tabs, modals, and pagination if data spans multiple sections of the "
    "page."
)


class FirecrawlAdapter:
    """
    AI Fetcher backed by Firecrawl's FIRE-1 agent.

    The adapter satisfies the DataCaptureAdapter Protocol:
      - fetch_raw: invokes Firecrawl scrape_url with agent + json options
      - parse: turns the structured JSON into a ParsedDataCaptureResult
      - score: tier-weighted completeness over the parsed presence map
    """

    name: str = "firecrawl"
    supported_domains: List[str] = ["*"]

    def _get_app(self):
        """Lazy-init the Firecrawl v2 SDK client."""
        if not settings.firecrawl_enabled():
            raise RuntimeError("Firecrawl is disabled (no API key configured)")
        from firecrawl import Firecrawl

        return Firecrawl(api_key=settings.FIRECRAWL_API_KEY)

    async def fetch_raw(self, request: DataCaptureRequest) -> RawDataCaptureResult:
        """
        Run a Firecrawl /v2/agent extraction against the URL.

        The agent navigates the page using natural-language reasoning + the
        prompt + schema, returning structured fields in `AgentResponse.data`.
        The SDK call is blocking (internally polls until the agent reaches
        completed / failed / cancelled).
        """
        start_time = time.time()

        if not settings.firecrawl_enabled():
            return RawDataCaptureResult(
                adapter_name=self.name,
                url=request.url,
                status=AdapterStatus.FAILED,
                error_message="Firecrawl adapter disabled (no API key configured)",
                duration_ms=int((time.time() - start_time) * 1000),
            )

        # Allow caller to override or augment the prompt (used by WF B's
        # focused-attempt path, which sends a prompt highlighting fields the
        # default attempt missed).
        prompt = request.prompt or _AGENT_PROMPT

        try:
            import asyncio

            app = self._get_app()
            # Firecrawl.agent() is blocking — internally polls every
            # poll_interval seconds until status ∈ {completed, failed,
            # cancelled} or `timeout` (seconds) elapses. Run in a thread
            # so the asyncio loop isn't blocked.
            result = await asyncio.to_thread(
                app.agent,
                [request.url],
                prompt=prompt,
                schema=PROPERTY_EXTRACTION_SCHEMA,
                model=settings.FIRECRAWL_AGENT_MODEL,
                max_credits=settings.FIRECRAWL_AGENT_MAX_CREDITS,
                strict_constrain_to_urls=True,
                timeout=settings.FIRECRAWL_AGENT_TIMEOUT_SECONDS,
                poll_interval=2,
            )
        except Exception as e:
            logger.error(
                f"Firecrawl /v2/agent fetch_raw failed for {request.url}: {e}",
                exc_info=True,
            )
            return RawDataCaptureResult(
                adapter_name=self.name,
                url=request.url,
                status=AdapterStatus.FAILED,
                error_message=str(e),
                duration_ms=int((time.time() - start_time) * 1000),
            )

        duration_ms = int((time.time() - start_time) * 1000)

        # result is an AgentResponse pydantic model:
        #   .id, .status (processing|completed|failed), .data (Any),
        #   .error (str|None), .credits_used (int|None),
        #   .expires_at (datetime|None)
        # Normalise to a dict for logging / payload preservation. Use
        # mode='json' so datetime/UUID are serialised to strings — the
        # payload ends up in fetcher_runs.payload_json (jsonb) and a bare
        # datetime breaks the FastAPI/SQLAlchemy json serialiser with an
        # uncaught TypeError on the PARTIAL/FAILED branches below.
        if hasattr(result, "model_dump"):
            payload_obj: Dict[str, Any] = result.model_dump(mode="json")
        elif isinstance(result, dict):
            payload_obj = result
        else:
            payload_obj = {"raw": str(result)}

        status = payload_obj.get("status")
        json_data = payload_obj.get("data")

        # The agent may report `processing` if the SDK's internal poll
        # timed out before completion. Treat that as PARTIAL — no usable
        # data yet, but not a hard error.
        if status != "completed" or not isinstance(json_data, dict):
            err = (
                payload_obj.get("error")
                or (
                    "Firecrawl /v2/agent did not return structured data "
                    f"(status={status!r})"
                )
            )
            logger.warning(
                f"Firecrawl /v2/agent partial for {request.url}: "
                f"status={status!r} keys={list(payload_obj)[:10]} "
                f"credits_used={payload_obj.get('credits_used')}"
            )
            return RawDataCaptureResult(
                adapter_name=self.name,
                url=request.url,
                status=(
                    AdapterStatus.FAILED if status == "failed"
                    else AdapterStatus.PARTIAL
                ),
                payload=payload_obj,
                error_message=err,
                duration_ms=duration_ms,
            )

        # Hash the structured payload for caching / dedupe.
        try:
            content_hash = hashlib.sha256(
                json.dumps(json_data, sort_keys=True, default=str).encode()
            ).hexdigest()
        except Exception:
            content_hash = None

        # Preserve the structured fields under `payload["json"]` so .parse()
        # below can read them without re-parsing — same contract the
        # previous FIRE-1 adapter exposed.
        return RawDataCaptureResult(
            adapter_name=self.name,
            url=request.url,
            status=AdapterStatus.SUCCESS,
            payload={
                "json": json_data,
                "agent_id": payload_obj.get("id"),
                "credits_used": payload_obj.get("credits_used"),
                "model": payload_obj.get("model") or settings.FIRECRAWL_AGENT_MODEL,
            },
            content_hash=content_hash,
            duration_ms=duration_ms,
        )

    async def parse(self, raw: RawDataCaptureResult) -> ParsedDataCaptureResult:
        """
        Extract canonical fields from the FIRE-1 structured response.

        Unlike the old adapter (which returned booleans), this returns real
        VALUES — strings, numbers, arrays. The completeness scorer treats
        meaningful values (non-null, non-empty) as present.
        """
        if raw.status not in (AdapterStatus.SUCCESS, AdapterStatus.PARTIAL):
            return ParsedDataCaptureResult(
                adapter_name=self.name,
                url=raw.url,
                status=AdapterStatus.FAILED,
                error_message=raw.error_message or "No payload to parse",
            )

        if not isinstance(raw.payload, dict):
            return ParsedDataCaptureResult(
                adapter_name=self.name,
                url=raw.url,
                status=AdapterStatus.FAILED,
                error_message="Firecrawl payload was not a dict",
            )

        fields: Dict[str, Any] = {}
        json_data = raw.payload.get("json")
        if isinstance(json_data, dict):
            fields = {k: v for k, v in json_data.items() if v is not None}

        # Always set source_url to what we asked the agent to scrape, in
        # case the agent returns null for it.
        fields.setdefault("source_url", raw.url)

        # Compute presence using the field_registry's canonical rules.
        presence = compute_field_presence(fields)
        missing = [f for f, p in presence.items() if not p]

        return ParsedDataCaptureResult(
            adapter_name=self.name,
            url=raw.url,
            status=AdapterStatus.SUCCESS if fields else AdapterStatus.PARTIAL,
            fields=fields,
            field_presence=presence,
            image_urls=fields.get("image_urls") or [],
            floorplan_urls=fields.get("floorplan_urls") or [],
            missing_fields=missing,
        )

    async def score(self, parsed: ParsedDataCaptureResult) -> CompletenessScore:
        """Tier-weighted completeness score over the parsed presence map."""
        if parsed.status not in (AdapterStatus.SUCCESS, AdapterStatus.PARTIAL):
            return CompletenessScore(overall=0.0)
        return compute_completeness_score(parsed.field_presence)


# Global instance (registered in data_capture.ai_fetchers via the
# h9f5e3a8b1c2 migration's seed → adapter_path
# 'data_capture_service.adapters.firecrawl.firecrawl_adapter:firecrawl_adapter').
firecrawl_adapter = FirecrawlAdapter()
