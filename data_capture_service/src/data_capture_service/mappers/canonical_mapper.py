"""
Canonical Mapper — maps parsed adapter output to canonical property snapshot.

Priority 0-3 fields → real columns on CanonicalPropertySnapshot.
Priority 4+ fields → extras_json JSONB column.
Media items → CanonicalMedia rows.
"""

import logging
from typing import Any, Dict, List, Tuple

from data_capture_service.adapters.base import ParsedDataCaptureResult
from data_capture_service.services.field_registry import (
    CANONICAL_COLUMN_FIELDS,
    EXTRAS_FIELDS,
)

logger = logging.getLogger(__name__)

# Mapping from canonical field names to CanonicalPropertySnapshot column names.
# Most map 1:1, but some have slight differences.
FIELD_TO_COLUMN: Dict[str, str] = {
    "address_road": "address_road",
    "price": "price",
    "price_text": "price_text",
    "source_url": "source_url",  # Not a real column on snapshot, set separately
    "address_town": "address_town",
    "bedrooms": "bedrooms",
    "estate_agent_name": "estate_agent_name",
    "agent_address": "agent_address",
    "transaction_type": "transaction_type",
    "bathrooms": "bathrooms",
    "property_type": "property_type",
    "full_address": "full_address",
    "postcode": "postcode",
    "description": "description",
    "rightmove_url": "rightmove_url",
    # Note: image_urls and floorplan_urls are stored as CanonicalMedia rows
}

# Fields that are stored as media items rather than columns
MEDIA_FIELDS = {"image_urls", "floorplan_urls", "video_urls"}


def map_to_canonical(
    parsed: ParsedDataCaptureResult,
    url: str,
    adapter_name: str,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    """
    Map parsed adapter result to canonical format.

    Returns:
        (column_fields, extras_json, media_items)

        - column_fields: dict of {column_name: value} for Priority 0-3 fields
        - extras_json: dict of {field_name: value} for Priority 4+ fields
        - media_items: list of dicts for CanonicalMedia rows
    """
    fields = parsed.fields

    # --- Priority 0-3 → real columns ---
    column_fields: Dict[str, Any] = {}
    for field_name in CANONICAL_COLUMN_FIELDS:
        if field_name in MEDIA_FIELDS:
            continue  # Handled separately as media items
        column_name = FIELD_TO_COLUMN.get(field_name, field_name)
        value = fields.get(field_name)
        if value is not None:
            column_fields[column_name] = value

    # --- Priority 4+ → extras_json ---
    extras_json: Dict[str, Any] = {}
    for field_name in EXTRAS_FIELDS:
        if field_name in MEDIA_FIELDS:
            continue
        value = fields.get(field_name)
        if value is not None:
            extras_json[field_name] = value

    # Also include any unknown fields from the parsed data in extras
    known_fields = CANONICAL_COLUMN_FIELDS | EXTRAS_FIELDS | MEDIA_FIELDS
    for field_name, value in fields.items():
        if field_name not in known_fields and value is not None:
            extras_json[field_name] = value

    # --- Media items ---
    media_items: List[Dict[str, Any]] = []

    # Property photos
    for i, img_url in enumerate(parsed.image_urls):
        media_items.append(
            {
                "media_type": "photo",
                "url": img_url,
                "sort_order": i,
                "is_high_res": _is_high_res_url(img_url),
            }
        )

    # Floorplans
    for i, fp_url in enumerate(parsed.floorplan_urls):
        media_items.append(
            {
                "media_type": "floorplan",
                "url": fp_url,
                "sort_order": i,
                "is_high_res": False,
            }
        )

    # Videos (from extras if present)
    video_urls = fields.get("video_urls", [])
    if isinstance(video_urls, list):
        for i, vid_url in enumerate(video_urls):
            if isinstance(vid_url, str) and vid_url.startswith("http"):
                media_items.append(
                    {
                        "media_type": "video",
                        "url": vid_url,
                        "sort_order": i,
                        "is_high_res": False,
                    }
                )

    logger.info(
        f"Canonical mapping: {len(column_fields)} columns, "
        f"{len(extras_json)} extras, {len(media_items)} media items"
    )

    return column_fields, extras_json, media_items


def _is_high_res_url(url: str) -> bool:
    """Simple heuristic to detect if an image URL is likely high-resolution."""
    high_res_indicators = [
        "/1024/", "/1280/", "/1920/", "/2048/",
        "_xl.", "_large.", "_hires.", "_full.",
        "max_", "original",
    ]
    url_lower = url.lower()
    return any(indicator in url_lower for indicator in high_res_indicators)
