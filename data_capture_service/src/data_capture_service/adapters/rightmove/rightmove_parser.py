"""
Rightmove result parser — handles the data_capture_rightmove_service
`/fetch/combined` response shape and maps it to our canonical field set.

Why this exists: the Rightmove proxy is a `source_type='proxy'` fetcher in
the registry, and the previous WF1 path tried to extract canonical fields
from its response with a generic JS code node. That failed because the
proxy returns a multi-endpoint envelope:

    {
      "property_id": <int>,
      "property_url": <str>,
      "results": [
        {
          "api_endpoint": "properties/details",
          "raw_data": { "data": {...rightmove API response (camelCase)...} }
        },
        { "api_endpoint": "properties/photos", "raw_data": {...} },
        ...
      ]
    }

The data we need is spread across multiple `results[*].raw_data` blobs —
no single `canonical` block. This parser walks those, recognises endpoint
shapes, and assembles the canonical field dict our scoring expects.

Registered as the "rightmove" parser in services.parser_registry; the
Rightmove fetcher row's metadata_json carries `parser_name: "rightmove"`
so /fetchers/validate auto-picks this when called with that fetcher_id.
"""

from typing import Any, Dict, List, Tuple

# Mapping from Rightmove camelCase / snake_case keys → canonical names.
# Many Rightmove keys are camelCase in the raw API response; the proxy
# stores them as-is in `raw_data`. We accept both forms defensively.
_DETAIL_KEY_MAP: Dict[str, str] = {
    # Identity
    "identifier": "property_id",
    "id": "property_id",
    "propertyId": "property_id",
    "property_id": "property_id",
    # Transaction kind
    "transactionType": "transaction_type",
    "transaction_type": "transaction_type",
    # Bedrooms / bathrooms
    "bedrooms": "bedrooms",
    "bathrooms": "bathrooms",
    # Address bits
    "address": "full_address",
    "displayAddress": "full_address",
    "addressLine1": "address_road",
    "address_line_1": "address_road",
    "addressLine2": "address_town",
    "town": "address_town",
    "city": "address_town",
    "postcode": "postcode",
    "postCode": "postcode",
    # Property type
    "propertyDisplayType": "property_type",
    "property_display_type": "property_type",
    "propertySubType": "property_type",
    # Description
    "fullDescription": "description",
    "full_description": "description",
    "description": "description",
    "propertyPhrase": "description_short",
    "property_phrase": "description_short",
    "shortDescription": "description_short",
    # Lifecycle
    "listingUpdateReason": "last_update_reason",
    "listing_update_reason": "last_update_reason",
    "lastUpdated": "last_update_reason",
    "publishedOn": "created_date",
    "addedOn": "created_date",
    # External link
    "propertyUrl": "rightmove_url",
    "property_url": "rightmove_url",
}


def _canonicalise_detail_block(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map the keys of a `properties/details` raw_data.data block onto canonical
    field names. Returns a flat dict with the canonical keys we recognised;
    silent on unrecognised keys.
    """
    out: Dict[str, Any] = {}
    for raw_key, value in data.items():
        canon = _DETAIL_KEY_MAP.get(raw_key)
        if canon and value is not None:
            out[canon] = value
    return out


def _extract_price(data: Dict[str, Any]) -> Any:
    """
    Rightmove returns price under a `prices` block (lowest, displayPrice, etc.)
    OR sometimes a flat `priceText` / `displayPrice`. Try a few likely paths.
    """
    prices = data.get("prices") or data.get("price")
    if isinstance(prices, dict):
        return (
            prices.get("displayPrice")
            or prices.get("primaryPrice")
            or prices.get("price")
            or prices.get("amount")
            or prices.get("priceQualifier")
        )
    if isinstance(prices, str):
        return prices
    for key in (
        "priceText",
        "displayPrice",
        "primaryPriceText",
        "priceQualifier",
    ):
        if key in data and data[key]:
            return data[key]
    return None


def _extract_estate_agent(data: Dict[str, Any]) -> Tuple[Any, Any]:
    """
    Rightmove typically nests agent info under `customer`, `branch`,
    `contactInformation`, or `agent`. Try several likely shapes.
    """
    sources = [
        data.get("customer"),
        data.get("branch"),
        data.get("agent"),
        data.get("contactInformation"),
    ]
    for src in sources:
        if not isinstance(src, dict):
            continue
        name = (
            src.get("branchDisplayName")
            or src.get("brandPlusLogoURI")
            or src.get("name")
            or src.get("displayName")
        )
        addr = (
            src.get("branchDisplayAddress")
            or src.get("displayAddress")
            or src.get("address")
        )
        if name or addr:
            return name, addr
    return None, None


def _extract_image_urls(data: Dict[str, Any]) -> List[str]:
    """
    Pull image URLs from any of: `images`, `propertyImages.images`, `photos`,
    `media`. Each entry may be a string URL or a dict with `url` / `srcUrl`
    / `thumbnailUrl` etc.
    """
    candidates: List[Any] = []
    for key in ("images", "photos", "media"):
        v = data.get(key)
        if isinstance(v, list):
            candidates.extend(v)
    pi = data.get("propertyImages")
    if isinstance(pi, dict):
        v = pi.get("images") or pi.get("photos") or []
        if isinstance(v, list):
            candidates.extend(v)

    urls: List[str] = []
    for item in candidates:
        if isinstance(item, str) and item.startswith("http"):
            urls.append(item)
        elif isinstance(item, dict):
            for k in (
                "url",
                "srcUrl",
                "src",
                "imageUrl",
                "originalUrl",
                "originalUri",
                "fullSizeUrl",
                "thumbnailUrl",
            ):
                if item.get(k):
                    urls.append(item[k])
                    break
    return urls


def _extract_floorplan_urls(data: Dict[str, Any]) -> List[str]:
    """Pull floorplan URLs similarly to images."""
    candidates: List[Any] = []
    for key in ("floorplans", "floorplanImages", "floor_plans"):
        v = data.get(key)
        if isinstance(v, list):
            candidates.extend(v)
    pi = data.get("propertyImages")
    if isinstance(pi, dict):
        v = pi.get("floorplans") or []
        if isinstance(v, list):
            candidates.extend(v)

    urls: List[str] = []
    for item in candidates:
        if isinstance(item, str) and item.startswith("http"):
            urls.append(item)
        elif isinstance(item, dict):
            for k in ("url", "srcUrl", "src", "imageUrl", "originalUrl"):
                if item.get(k):
                    urls.append(item[k])
                    break
    return urls


def _find_results_array(payload: Dict[str, Any]) -> List[Any]:
    """
    Locate the `results: [...]` array inside the payload. Handles three
    common wrappings:

    1. Direct: payload itself has `results` at top level (proxy raw response).
    2. Snapshot wrapper: `payload.data.results` — what status_notifier
       writes to S3 ({super_id, context, status, summary, metadata, data}).
    3. n8n Extract Canonical Fields wrapper: `payload.fields.results`.

    Returns the first non-empty list found; otherwise an empty list.
    """
    for path in (
        ("results",),
        ("data", "results"),
        ("fields", "results"),
        ("payload", "results"),
        ("payload", "data", "results"),
        ("payload", "fields", "results"),
    ):
        cur: Any = payload
        for key in path:
            if isinstance(cur, dict):
                cur = cur.get(key)
            else:
                cur = None
                break
        if isinstance(cur, list) and cur:
            return cur
    return []


def _find_inner_envelope(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Locate the inner rightmove envelope (the one with property_id /
    property_url at top level) under any of the known wrappers. Falls
    back to the payload itself if no wrapper is detected.
    """
    for path in (
        ("data",),
        ("fields",),
        ("payload", "data"),
        ("payload", "fields"),
        ("payload",),
    ):
        cur: Any = payload
        for key in path:
            if isinstance(cur, dict):
                cur = cur.get(key)
            else:
                cur = None
                break
        if isinstance(cur, dict) and (
            "property_url" in cur or "property_id" in cur or "results" in cur
        ):
            return cur
    return payload


def _walk_results(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Yield each `raw_data.data` block from `results[*]`, regardless of
    api_endpoint. Some Rightmove envelopes wrap one more level:
    raw_data → {data: {...}}; some are direct: raw_data → {...}.

    Searches multiple wrapper paths via `_find_results_array` so the
    parser works whether it's fed:
      - the raw proxy response ({results: [...]})
      - a status_notifier snapshot ({data: {results: [...]}})
      - an n8n Extract Canonical Fields output ({fields: {results: [...]}})
    """
    out: List[Dict[str, Any]] = []
    results = _find_results_array(payload)
    for item in results:
        if not isinstance(item, dict):
            continue
        raw = item.get("raw_data")
        if isinstance(raw, dict):
            data = raw.get("data") if isinstance(raw.get("data"), dict) else raw
        else:
            data = None
        if isinstance(data, dict):
            out.append(data)
    return out


def parse_rightmove_result(
    payload: Dict[str, Any],
    source_url: str,
) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """
    Entry point matching the parser_registry contract:
    `(payload, source_url) -> (fields, image_urls, floorplan_urls)`.

    Walks every result block, applies key mapping + price/agent/media
    extraction, and merges into a single canonical dict. Fields filled
    by a later block override `None` values from earlier blocks but
    don't overwrite already-populated values.
    """
    fields: Dict[str, Any] = {}
    image_urls: List[str] = []
    floorplan_urls: List[str] = []

    def _merge(into: Dict[str, Any], src: Dict[str, Any]) -> None:
        for k, v in src.items():
            if v in (None, "", []):
                continue
            if not into.get(k):
                into[k] = v

    # Top-level metadata — look in the inner envelope (handles snapshot /
    # n8n wrappers as well as the bare proxy response shape).
    inner = _find_inner_envelope(payload)
    if isinstance(inner.get("property_url"), str):
        fields["source_url"] = inner["property_url"]
        fields.setdefault("rightmove_url", inner["property_url"])
    if "property_id" in inner:
        fields.setdefault("property_id", inner["property_id"])

    # Walk results
    blocks = _walk_results(payload)
    if not blocks:
        # Single-block fallback (e.g. test fixtures without the results wrapper).
        # Try common wrapper paths plus the raw payload itself.
        for candidate in (inner, payload.get("data"), payload):
            if isinstance(candidate, dict) and any(
                k in candidate
                for k in (
                    "identifier",
                    "bedrooms",
                    "bathrooms",
                    "address",
                    "prices",
                    "price",
                )
            ):
                blocks = [candidate]
                break

    for block in blocks:
        _merge(fields, _canonicalise_detail_block(block))

        # Price (may live under details or a separate prices endpoint)
        price = _extract_price(block)
        if price and not fields.get("price"):
            fields["price"] = price

        # Estate agent
        agent_name, agent_addr = _extract_estate_agent(block)
        if agent_name and not fields.get("estate_agent_name"):
            fields["estate_agent_name"] = agent_name
        if agent_addr and not fields.get("agent_address"):
            fields["agent_address"] = agent_addr

        # Images / floorplans (accumulate across blocks; dedupe later)
        image_urls.extend(_extract_image_urls(block))
        floorplan_urls.extend(_extract_floorplan_urls(block))

    # Dedupe while preserving order
    image_urls = list(dict.fromkeys(image_urls))
    floorplan_urls = list(dict.fromkeys(floorplan_urls))

    # Surface media into fields too, so the validator's presence check
    # for image_urls / floorplan_urls passes when arrays are non-empty.
    if image_urls and not fields.get("image_urls"):
        fields["image_urls"] = image_urls
    if floorplan_urls and not fields.get("floorplan_urls"):
        fields["floorplan_urls"] = floorplan_urls

    # Default source_url to the URL the caller passed if not already set
    if not fields.get("source_url"):
        fields["source_url"] = source_url

    return fields, image_urls, floorplan_urls
