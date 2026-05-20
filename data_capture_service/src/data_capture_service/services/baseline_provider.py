"""
Firecrawl Baseline Provider — NOT an adapter in the fallback chain.

Runs before any adapter to establish a ground-truth baseline of what data
a property page contains. Used by the validation gate for presence-check
comparisons against adapter output.

Feature-flagged via DATA_CAPTURE_SERVICE_FIRECRAWL_API_KEY presence.
"""

import logging
import re
import time
from typing import Any, Dict, Optional

from data_capture_service.adapters.base import AdapterStatus, BaselineResult
from data_capture_service.config import settings

logger = logging.getLogger(__name__)


def parse_markdown_for_field_presence(markdown: str) -> Dict[str, bool]:
    """
    Lightweight regex-based detection of field presence from Firecrawl markdown.

    This is intentionally simple — we only need to know IF a field is present
    on the page, not extract precise values. The validation gate uses these
    booleans to check adapter output against known page content.
    """
    if not markdown:
        return {}

    text = markdown
    lower = text.lower()

    # --- Price detection ---
    has_price = bool(re.search(r"£\s?[\d,]+", text))
    if not has_price:
        # Fallback: look for "price" heading followed by a number
        has_price = bool(re.search(r"price.*?[\d,]+", lower))

    # --- Address detection ---
    # UK postcode pattern
    has_postcode = bool(
        re.search(
            r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}",
            text,
            re.IGNORECASE,
        )
    )
    # Street words
    street_words = [
        "road", "street", "lane", "avenue", "drive", "close", "way",
        "crescent", "court", "terrace", "grove", "place", "gardens",
    ]
    has_street = any(f" {w}" in lower for w in street_words)
    has_address = has_postcode or has_street

    # --- Image detection ---
    # Count markdown images ![...](...) and plain image URLs
    image_patterns = re.findall(r"!\[.*?\]\(.*?\)", text)
    image_url_patterns = re.findall(
        r"https?://\S+\.(?:jpg|jpeg|png|webp|gif)", text, re.IGNORECASE
    )
    image_count = len(set(image_patterns + image_url_patterns))
    has_images = image_count > 0

    # --- Floorplan detection ---
    has_floorplan = bool(re.search(r"floor\s*plan", lower))

    # --- Bedrooms ---
    has_bedrooms = bool(re.search(r"\d+\s*bed(?:room)?s?", lower))

    # --- Bathrooms ---
    has_bathrooms = bool(re.search(r"\d+\s*bath(?:room)?s?", lower))

    # --- Agent ---
    has_agent = bool(
        re.search(r"(?:estate\s+agent|marketed\s+by|listed\s+by|contact)", lower)
    )

    # --- Property type ---
    property_types = [
        "detached", "semi-detached", "terraced", "end of terrace",
        "flat", "apartment", "maisonette", "bungalow", "cottage",
        "house", "studio", "penthouse",
    ]
    has_property_type = any(pt in lower for pt in property_types)

    # --- Description ---
    # Assume description present if there's a reasonable amount of text
    paragraphs = [p for p in text.split("\n\n") if len(p.strip()) > 100]
    has_description = len(paragraphs) >= 1

    # --- Transaction type ---
    has_transaction_type = bool(
        re.search(r"(?:for sale|to rent|to let|for rent|sale|lettings?)", lower)
    )

    return {
        "price": has_price,
        "address_road": has_address,
        "postcode": has_postcode,
        "image_urls": has_images,
        "floorplan_urls": has_floorplan,
        "source_url": True,  # Always present (we have the URL)
        "bedrooms": has_bedrooms,
        "bathrooms": has_bathrooms,
        "estate_agent_name": has_agent,
        "property_type": has_property_type,
        "description": has_description,
        "transaction_type": has_transaction_type,
        "address_town": has_address,  # Approximate: if we found address, town is likely
        "full_address": has_address,
        "_image_count": image_count,  # Extra metadata for validation gate
    }


class FirecrawlBaselineProvider:
    """
    Firecrawl baseline provider for establishing ground-truth field presence.

    Uses Firecrawl's DATA_CAPTURE mode (synchronous, ~3s, ~3 credits) to fetch
    page markdown, then runs regex-based field detection.

    This is NOT an adapter — it runs before the adapter chain and feeds
    the validation gate.
    """

    def __init__(self):
        self._app = None

    def _get_app(self):
        """Lazy-initialize Firecrawl v2 SDK client."""
        if self._app is None:
            try:
                from firecrawl import Firecrawl

                self._app = Firecrawl(api_key=settings.FIRECRAWL_API_KEY)
            except ImportError:
                logger.error("firecrawl-py package not installed")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize Firecrawl client: {e}")
                raise
        return self._app

    async def fetch_baseline(self, url: str) -> BaselineResult:
        """
        Fetch baseline field presence from a property URL using Firecrawl data_capture mode.

        Returns a BaselineResult with field_presence booleans that the validation
        gate can compare against adapter output.
        """
        if not settings.firecrawl_enabled():
            logger.warning("Firecrawl baseline provider is disabled (no API key)")
            return BaselineResult(
                url=url,
                status=AdapterStatus.FAILED,
                error_message="Firecrawl baseline provider disabled (no API key)",
            )

        start_time = time.time()
        try:
            app = self._get_app()

            # Firecrawl v2 scrape is synchronous — run in thread pool to
            # avoid blocking. Returns a Document pydantic model with
            # `.markdown` populated when formats=["markdown"].
            import asyncio

            result = await asyncio.to_thread(
                app.scrape,
                url,
                formats=["markdown"],
                only_main_content=True,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            # v2 SDK returns a Document — markdown is an attribute. Fall
            # back to dict access if a future SDK release changes that.
            markdown = None
            if hasattr(result, "markdown"):
                markdown = result.markdown
            elif isinstance(result, dict):
                markdown = result.get("markdown", "")
            elif hasattr(result, "model_dump"):
                data = result.model_dump()
                markdown = data.get("markdown", "")

            if not markdown:
                logger.warning(f"Firecrawl returned no markdown for {url}")
                return BaselineResult(
                    url=url,
                    status=AdapterStatus.PARTIAL,
                    error_message="No markdown content returned",
                    duration_ms=duration_ms,
                )

            # Parse markdown for field presence
            field_presence = parse_markdown_for_field_presence(markdown)
            image_count = field_presence.pop("_image_count", 0)

            logger.info(
                f"Firecrawl baseline for {url}: "
                f"{sum(1 for v in field_presence.values() if v)}/{len(field_presence)} fields detected, "
                f"{image_count} images, {duration_ms}ms"
            )

            return BaselineResult(
                url=url,
                status=AdapterStatus.SUCCESS,
                markdown=markdown,
                field_presence=field_presence,
                image_count=image_count,
                has_price=field_presence.get("price", False),
                has_address=field_presence.get("address_road", False),
                has_floorplan=field_presence.get("floorplan_urls", False),
                duration_ms=duration_ms,
                credits_used=3,  # Firecrawl data_capture mode is ~3 credits
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Firecrawl baseline failed for {url}: {e}")
            return BaselineResult(
                url=url,
                status=AdapterStatus.FAILED,
                error_message=str(e),
                duration_ms=duration_ms,
            )


# Global instance
firecrawl_baseline_provider = FirecrawlBaselineProvider()
