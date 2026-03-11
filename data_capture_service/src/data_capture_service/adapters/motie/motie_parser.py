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
    ],
    "price": ["price", "price_text", "asking_price"],
    "price_text": ["price_text", "price_raw", "price"],
    "image_urls": [
        "image_urls",
        "images",
        "photo_urls",
        "property_images",
        "property_photos",
    ],
    "floorplan_urls": [
        "floorplan_images_urls",
        "floorplan_urls",
        "floorplans",
        "floor_plan_urls",
    ],
    "source_url": ["source_url", "url", "page_url", "listing_url"],
    "address_town": ["address_town", "town", "city", "locality"],
    "bedrooms": ["bedrooms_number", "bedrooms", "beds", "num_bedrooms"],
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
    "bathrooms": ["bathrooms_number", "bathrooms", "baths", "num_bathrooms"],
    "property_type": ["type", "property_type", "house_type"],
    "created_date": ["created", "created_date", "listed_date", "came_to_market"],
    "full_address": ["address_full", "full_address", "complete_address"],
    "postcode": ["address_postcode", "postcode", "zip_code", "postal_code"],
    "description": ["description_full", "description", "full_description"],
    "rightmove_url": ["property_url", "rightmove_url", "listing_url"],
    "description_short": ["description_short", "short_description", "summary"],
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
        "availability",
        "status",
    ],
    "last_update_reason": [
        "last_update_reason",
        "last_updated",
        "update_reason",
    ],
    "epcs": ["epcs", "epc", "epc_rating", "energy_rating"],
    "train_station_nearby": [
        "train_station_nearby",
        "nearest_station",
        "transport",
    ],
    "video_urls": ["video_urls", "videos", "virtual_tour"],
    "access": ["access"],
    "accessibility": ["accessibility"],
    "flood_risk": ["flood_risk"],
    "heating": ["heating", "heating_type"],
    "listed": ["listed", "listed_building"],
    "restrictions": ["restrictions"],
    "shared_ownership": ["shared_ownership"],
    "utilities": ["utilities"],
}


def _extract_field(data: Dict[str, Any], possible_keys: List[str]) -> Any:
    """Try each possible key in order, returning the first non-null match."""
    for key in possible_keys:
        value = data.get(key)
        if value is not None:
            # Normalize "null" strings to None
            if isinstance(value, str) and value.strip().lower() in ("null", "none", "n/a"):
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
    fields["bedrooms"] = _coerce_int(
        _extract_field(data, FIELD_MAPPING["bedrooms"])
    )
    fields["bathrooms"] = _coerce_int(
        _extract_field(data, FIELD_MAPPING["bathrooms"])
    )

    logger.info(
        f"Parsed Motie result: {len(fields)} fields, "
        f"{len(image_urls)} images, {len(floorplan_urls)} floorplans"
    )

    return fields, image_urls, floorplan_urls
