"""
Motie result parser — handles variable JSON output from Motie and maps to
canonical field names used by the data_capture service.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Mapping from various Motie output keys to our canonical field names.
# Motie's output is not strictly standardized, so we check multiple possible keys.
FIELD_MAPPING: Dict[str, List[str]] = {
    "address_road": [
        "address_road_name",
        "address_road",
        "road",
        "street",
        "address_line_1",
        # Prompt variant: "Address (Road name)" → normalized
        "address_road_name",
    ],
    "price": ["price", "price_text", "asking_price"],
    "price_text": ["price_text", "price_raw", "price"],
    "image_urls": [
        "image_urls",
        "images",
        "photo_urls",
        "property_images",
        "property_photos",
        # Prompt variant: "Image(s) URL(s) (ALL, High Res)" → normalized
        "images_urls_all_high_res",
        "images_urls",
        "image_url",
    ],
    "floorplan_urls": [
        "floorplan_images_urls",
        "floorplan_urls",
        "floorplans",
        "floor_plan_urls",
        # Prompt variant: "Floorplan(s) Images URL(s)" → normalized
        "floorplans_images_urls",
        "floorplan_images",
    ],
    "source_url": [
        "source_url",
        "url",
        "page_url",
        "listing_url",
        "source_url",
    ],
    "address_town": [
        "address_town",
        "town",
        "city",
        "locality",
    ],
    "bedrooms": [
        "bedrooms_number",
        "bedrooms",
        "beds",
        "num_bedrooms",
    ],
    "estate_agent_name": [
        "estate_agent_name",
        "agent_name",
        "agent",
        "marketed_by",
        "listed_by",
    ],
    "agent_address": [
        "estate_agent_address",
        "agent_address",
        "agent_office",
    ],
    "transaction_type": [
        "transaction_type_details",
        "transaction_type",
        "listing_type",
        "sale_type",
    ],
    "bathrooms": [
        "bathrooms_number",
        "bathrooms",
        "baths",
        "num_bathrooms",
    ],
    "property_type": [
        "type",
        "property_type",
        "house_type",
        # Prompt variant: "Type (House, Detached etc)" → normalized
        "type_house_detached_etc",
    ],
    "created_date": [
        "created",
        "created_date",
        "listed_date",
        "came_to_market",
        # Prompt variant: "Created (came to market)" → normalized
        "created_came_to_market",
    ],
    "full_address": [
        "address_full",
        "full_address",
        "complete_address",
    ],
    "postcode": [
        "address_postcode",
        "postcode",
        "zip_code",
        "postal_code",
    ],
    "description": [
        "description_full",
        "description",
        "full_description",
    ],
    "rightmove_url": [
        "property_url",
        "rightmove_url",
        "rightmove_url",
    ],
    "description_short": [
        "description_short",
        "short_description",
        "summary",
    ],
    "size": ["size", "floor_area", "square_footage", "sqft"],
    "tenure": ["tenure", "ownership_type"],
    "garden": ["garden", "gardens", "outdoor_space"],
    "parking": ["parking", "parking_spaces"],
    "address_coordinates": [
        "address_location_coordinates",
        "coordinates",
        "lat_lng",
        "location",
    ],
    "status_availability": [
        "status_availability",
        "status_availability",
        "availability",
        "status",
    ],
    "last_update_reason": [
        "last_update_reason",
        "last_update_reason",
        "last_updated",
        "update_reason",
    ],
    "epcs": [
        "epcs",
        "epc",
        "epc_rating",
        "energy_rating",
    ],
    "train_station_nearby": [
        "train_station_nearby",
        "nearest_station",
        "transport",
    ],
    "video_urls": [
        "video_urls",
        "videos",
        "virtual_tour",
        # Prompt variant: "Video(s) URLs" → normalized
        "videos_urls",
    ],
    "access": ["access"],
    "accessibility": ["accessibility"],
    "flood_risk": ["flood_risk"],
    "heating": ["heating", "heating_type"],
    "listed": ["listed", "listed_building", "listed_"],
    "restrictions": ["restrictions"],
    "shared_ownership": ["shared_ownership"],
    "utilities": ["utilities"],
}


def _normalize_key(key: str) -> str:
    """
    Normalize a key to lowercase snake_case for matching.

    Handles keys like:
    - "Address (Road name)" → "address_road_name"
    - "Price" → "price"
    - "Image(s) URL(s) (ALL, High Res)" → "images_urls_all_high_res"
    - "Bedrooms (number)" → "bedrooms_number"
    - "estate_agent_name" → "estate_agent_name" (already normalized)
    """
    k = key.lower()
    # Remove (s) pluralization markers
    k = k.replace("(s)", "s")
    # Replace parenthesized content: "Address (Road name)" → "Address Road name"
    k = re.sub(r"[()&/,]", " ", k)
    # Collapse whitespace and replace with underscores
    k = re.sub(r"[\s\-]+", "_", k.strip())
    # Remove trailing/leading underscores
    k = k.strip("_")
    return k


def _normalize_data_keys(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a normalized copy of the data dict where all keys are lowercased
    and converted to snake_case. Also preserves original keys so both can match.
    """
    normalized: Dict[str, Any] = {}
    for key, value in data.items():
        # Keep original
        normalized[key] = value
        # Also add normalized version
        norm_key = _normalize_key(key)
        if norm_key != key:
            normalized[norm_key] = value
    return normalized


def _extract_field(data: Dict[str, Any], possible_keys: List[str]) -> Any:
    """Try each possible key in order, returning the first non-null match."""
    for key in possible_keys:
        value = data.get(key)
        if value is not None:
            # Normalize "null" strings to None
            if isinstance(value, str) and value.strip().lower() in (
                "null",
                "none",
                "n/a",
            ):
                continue
            return value
    return None


def _extract_urls_from_list(items: Any) -> List[str]:
    """
    Extract URL strings from various list formats:
    - List of strings: ["url1", "url2"]
    - List of dicts: [{"url": "url1"}, {"url": "url2"}]
    """
    if not items:
        return []
    if not isinstance(items, list):
        if isinstance(items, str):
            return [items]
        return []

    urls = []
    for item in items:
        if isinstance(item, str) and item.startswith("http"):
            urls.append(item)
        elif isinstance(item, dict):
            url = item.get("url") or item.get("src") or item.get("href", "")
            if url and isinstance(url, str):
                urls.append(url)
    return urls


def _coerce_int(value: Any) -> Optional[int]:
    """Attempt to convert a value to int."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        return int(match.group(0)) if match else None
    return None


def parse_motie_result(
    data: Dict[str, Any],
    source_url: str,
) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """
    Parse a Motie result JSON into canonical fields.

    Returns:
        (fields_dict, image_urls, floorplan_urls)

    The fields_dict maps canonical field names to their extracted values.
    """
    # Handle nested data structures — Motie sometimes wraps in "data" key
    if "data" in data and isinstance(data["data"], dict):
        data = data["data"]

    # Log raw keys from Motie for debugging field mapping issues
    raw_keys = list(data.keys())
    logger.info(f"Raw Motie JSON keys ({len(raw_keys)}): {raw_keys}")

    # Normalize all keys to snake_case so we can match regardless of format
    data = _normalize_data_keys(data)
    normalized_keys = [k for k in data.keys() if k not in raw_keys]
    if normalized_keys:
        logger.info(f"Normalized keys added: {normalized_keys}")

    fields: Dict[str, Any] = {}

    for canonical_name, possible_keys in FIELD_MAPPING.items():
        value = _extract_field(data, possible_keys)

        # Special handling for certain field types
        if canonical_name in ("bedrooms", "bathrooms"):
            value = _coerce_int(value)
        elif canonical_name in ("image_urls", "floorplan_urls", "video_urls", "epcs"):
            # Will handle these separately below
            pass
        else:
            fields[canonical_name] = value

    # Extract media URLs
    image_urls = _extract_urls_from_list(
        _extract_field(data, FIELD_MAPPING["image_urls"])
    )
    floorplan_urls = _extract_urls_from_list(
        _extract_field(data, FIELD_MAPPING["floorplan_urls"])
    )
    video_urls = _extract_urls_from_list(
        _extract_field(data, FIELD_MAPPING["video_urls"])
    )

    # Store URL lists in fields
    fields["image_urls"] = image_urls
    fields["floorplan_urls"] = floorplan_urls
    fields["video_urls"] = video_urls

    # Handle EPCs (might be list of dicts or a string)
    epcs_raw = _extract_field(data, FIELD_MAPPING["epcs"])
    if isinstance(epcs_raw, list):
        fields["epcs"] = epcs_raw
    elif isinstance(epcs_raw, (str, dict)):
        fields["epcs"] = [epcs_raw] if epcs_raw else []
    else:
        fields["epcs"] = []

    # Ensure source_url is set
    if not fields.get("source_url"):
        fields["source_url"] = source_url

    # Coerce numeric fields
    fields["bedrooms"] = _coerce_int(_extract_field(data, FIELD_MAPPING["bedrooms"]))
    fields["bathrooms"] = _coerce_int(_extract_field(data, FIELD_MAPPING["bathrooms"]))

    # Count non-None fields for meaningful logging
    present_fields = [
        k for k, v in fields.items() if v is not None and v != [] and v != ""
    ]
    missing_fields = [k for k, v in fields.items() if v is None or v == [] or v == ""]

    logger.info(
        f"Parsed Motie result: {len(present_fields)}/{len(fields)} fields present, "
        f"{len(image_urls)} images, {len(floorplan_urls)} floorplans"
    )
    logger.info(f"Present fields: {present_fields}")
    logger.info(f"Missing fields: {missing_fields}")

    return fields, image_urls, floorplan_urls
