"""
Firecrawl AI Fetcher Adapter.

Wraps the existing FirecrawlBaselineProvider so Firecrawl can be invoked as a
first-class AI fetcher (V2 architecture) — i.e. an adapter that can run
independently of the validation gate, with a configurable schema/prompt and
returning structured payload + parsed fields.

The legacy baseline provider keeps doing its baseline-detection job for the
existing data_capture_pipeline; this adapter is what the new
/ai-fetchers/firecrawl/run primitive routes through.
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
from data_capture_service.services.baseline_provider import (
    firecrawl_baseline_provider,
    parse_markdown_for_field_presence,
)
from data_capture_service.services.field_registry import (
    compute_completeness_score,
    compute_field_presence,
)

logger = logging.getLogger(__name__)


class FirecrawlAdapter:
    """
    AI Fetcher adapter wrapping Firecrawl.

    fetch_raw runs Firecrawl in markdown mode and returns the markdown payload.
    parse runs the same regex-based field-presence logic the baseline provider
    uses, plus optional LLM-driven extraction in future iterations.
    score uses the standard field_registry completeness scorer.

    For MVP this adapter delivers field PRESENCE (essential-data check), which is
    the only validation rule we're committed to in V2 (Rolf's "(a) baseline
    expectations" — schema + essential data).
    """

    name: str = "firecrawl"
    supported_domains: List[str] = ["*"]

    async def fetch_raw(self, request: DataCaptureRequest) -> RawDataCaptureResult:
        """Run Firecrawl scrape and return the markdown payload as raw."""
        start_time = time.time()

        if not settings.firecrawl_enabled():
            return RawDataCaptureResult(
                adapter_name=self.name,
                url=request.url,
                status=AdapterStatus.FAILED,
                error_message="Firecrawl adapter disabled (no API key configured)",
                duration_ms=int((time.time() - start_time) * 1000),
            )

        try:
            baseline = await firecrawl_baseline_provider.fetch_baseline(request.url)
        except Exception as e:
            logger.error(f"Firecrawl fetch_raw failed: {e}", exc_info=True)
            return RawDataCaptureResult(
                adapter_name=self.name,
                url=request.url,
                status=AdapterStatus.FAILED,
                error_message=str(e),
                duration_ms=int((time.time() - start_time) * 1000),
            )

        if baseline.status != AdapterStatus.SUCCESS or not baseline.markdown:
            return RawDataCaptureResult(
                adapter_name=self.name,
                url=request.url,
                status=baseline.status,
                error_message=baseline.error_message or "No markdown returned",
                duration_ms=baseline.duration_ms,
            )

        payload: Dict[str, Any] = {
            "markdown": baseline.markdown,
            "field_presence": baseline.field_presence,
            "image_count": baseline.image_count,
        }
        content_hash = hashlib.sha256(baseline.markdown.encode()).hexdigest()

        return RawDataCaptureResult(
            adapter_name=self.name,
            url=request.url,
            status=AdapterStatus.SUCCESS,
            payload=payload,
            markdown=baseline.markdown,
            content_hash=content_hash,
            duration_ms=baseline.duration_ms,
        )

    async def parse(self, raw: RawDataCaptureResult) -> ParsedDataCaptureResult:
        """Parse Firecrawl markdown into field presence + minimal field values."""
        if raw.status != AdapterStatus.SUCCESS or not raw.payload:
            return ParsedDataCaptureResult(
                adapter_name=self.name,
                url=raw.url,
                status=AdapterStatus.FAILED,
                error_message=raw.error_message or "No payload to parse",
            )

        markdown = raw.payload.get("markdown") or raw.markdown or ""
        if not markdown:
            return ParsedDataCaptureResult(
                adapter_name=self.name,
                url=raw.url,
                status=AdapterStatus.PARTIAL,
                error_message="Firecrawl returned no markdown content",
            )

        try:
            # Re-derive presence map (in case raw payload didn't include it)
            field_presence = raw.payload.get("field_presence") or (
                parse_markdown_for_field_presence(markdown)
            )
            field_presence.pop("_image_count", None)

            # MVP: Firecrawl adapter only delivers presence booleans, not extracted
            # field values. Field values come from coded fetchers (WF1) or future
            # LLM extraction layers added on top of this adapter.
            fields: Dict[str, Any] = {
                k: True if v else None for k, v in field_presence.items()
            }

            normalized_presence = compute_field_presence(fields)
            missing = [f for f, present in normalized_presence.items() if not present]

            return ParsedDataCaptureResult(
                adapter_name=self.name,
                url=raw.url,
                status=AdapterStatus.SUCCESS,
                fields=fields,
                field_presence=normalized_presence,
                missing_fields=missing,
            )

        except Exception as e:
            logger.error(f"Firecrawl parse failed: {e}", exc_info=True)
            return ParsedDataCaptureResult(
                adapter_name=self.name,
                url=raw.url,
                status=AdapterStatus.FAILED,
                error_message=str(e),
            )

    async def score(self, parsed: ParsedDataCaptureResult) -> CompletenessScore:
        """Standard completeness score over field presence."""
        if parsed.status != AdapterStatus.SUCCESS:
            return CompletenessScore(overall=0.0)
        return compute_completeness_score(parsed.field_presence)


# Global instance
firecrawl_adapter = FirecrawlAdapter()
