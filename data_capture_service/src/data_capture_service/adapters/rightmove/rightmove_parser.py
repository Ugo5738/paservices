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

import re
from typing import Any, Dict, List, Optional, Tuple

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


def _split_address(full_address: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Best-effort split of Rightmove's free-form `address` / `displayAddress`
    into (road, town). Rightmove typically formats it as
    "<road>, <town>, <outcode>" — e.g. "Illey Lane, Halesowen, B62".
    Anything that doesn't parse cleanly returns (None, None) so the caller
    can keep the original full_address without polluting road/town.
    """
    if not isinstance(full_address, str) or not full_address.strip():
        return None, None
    parts = [p.strip() for p in full_address.split(",") if p.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None, None


def _extract_coordinates(data: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """
    Pull lat/long from Rightmove's `location` block. Returns a small dict
    {lat, lng} so the validator counts address_coordinates as present.
    """
    loc = data.get("location")
    if not isinstance(loc, dict):
        return None
    lat = loc.get("latitude")
    lng = loc.get("longitude")
    if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
        return {"lat": float(lat), "lng": float(lng)}
    return None


def _extract_created_date(data: Dict[str, Any]) -> Optional[str]:
    """
    Rightmove doesn't expose a clean ISO date. Best signals (in order):
      1. analyticsInfo.added ("20250828" → "2025-08-28")
      2. listingHistory.listingUpdateReason regex ("Added on 27/08/2025"
         or "Reduced on 27/08/2025") — extract the date.
      3. listingUpdateReason at the top level (same regex).
    """
    analytics = data.get("analyticsInfo")
    if isinstance(analytics, dict):
        added = analytics.get("added")
        if isinstance(added, str) and len(added) == 8 and added.isdigit():
            return f"{added[0:4]}-{added[4:6]}-{added[6:8]}"

    candidates: List[str] = []
    history = data.get("listingHistory")
    if isinstance(history, dict):
        for v in history.values():
            if isinstance(v, str):
                candidates.append(v)
    if isinstance(data.get("listingUpdateReason"), str):
        candidates.append(data["listingUpdateReason"])

    for text in candidates:
        m = re.search(r"(\d{2})/(\d{2})/(\d{4})", text)
        if m:
            d, mth, y = m.groups()
            return f"{y}-{mth}-{d}"
    return None


def _extract_tenure(data: Dict[str, Any]) -> Optional[str]:
    """
    Rightmove's tenure lives under `salesInfo.tenureType` (BUY listings)
    OR a top-level `tenure.tenureType` (newer schema). Either form.
    """
    for src in (data.get("tenure"), data.get("salesInfo")):
        if isinstance(src, dict):
            t = src.get("tenureDisplayType") or src.get("tenureType")
            if isinstance(t, str) and t.strip():
                return t
    return None


def _extract_size(data: Dict[str, Any]) -> Optional[str]:
    """
    Read `size.primary` if it's a real value (skip placeholders like
    "Ask agent" — Rightmove uses these when the agent didn't supply
    sq ft / m²).
    """
    size = data.get("size")
    if isinstance(size, dict):
        primary = size.get("primary")
        if isinstance(primary, str) and primary.strip().lower() not in (
            "",
            "ask agent",
            "ask",
            "n/a",
        ):
            return primary
    sizings = data.get("sizings")
    if isinstance(sizings, list) and sizings:
        first = sizings[0]
        if isinstance(first, dict):
            return first.get("primary") or first.get("displayValue")
    return None


def _alias_present(entry: Any) -> bool:
    """
    Rightmove feature entries are `[{alias, displayText}]` lists. An entry
    counts as "present" when its alias is something other than 'ask' (the
    placeholder for "agent didn't supply").
    """
    if isinstance(entry, list):
        for it in entry:
            if isinstance(it, dict):
                alias = it.get("alias")
                if isinstance(alias, str) and alias.lower() not in ("ask", ""):
                    return True
        return False
    if isinstance(entry, dict):
        alias = entry.get("alias")
        return isinstance(alias, str) and alias.lower() not in ("ask", "")
    if isinstance(entry, bool):
        return entry
    if isinstance(entry, str):
        return entry.lower() not in ("ask", "")
    return False


def _alias_display(entry: Any) -> Optional[str]:
    """First non-'ask' displayText from a Rightmove feature list/dict."""
    if isinstance(entry, list):
        for it in entry:
            if isinstance(it, dict) and it.get("alias", "").lower() != "ask":
                return it.get("displayText") or it.get("alias")
        return None
    if isinstance(entry, dict):
        if entry.get("alias", "").lower() != "ask":
            return entry.get("displayText") or entry.get("alias")
    return None


def _extract_features_cluster(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Rightmove `features` block has a fixed set of sub-keys (parking, garden,
    accessibility, heating, electricity, water, sewerage, broadband, plus
    nested `obligations` and `risks`). This pulls each one into a canonical
    field, treating the 'ask agent' alias as missing.
    """
    out: Dict[str, Any] = {}
    feats = data.get("features")
    if not isinstance(feats, dict):
        return out

    # Direct boolean-ish features
    for key, canon in (
        ("parking", "parking"),
        ("garden", "garden"),
        ("accessibility", "accessibility"),
        ("heating", "heating"),
    ):
        entry = feats.get(key)
        if _alias_present(entry):
            out[canon] = _alias_display(entry) or True

    # Utilities — Rightmove splits across electricity/water/sewerage/broadband.
    # Aggregate any that are populated into a small dict so the field counts
    # as present once at least one utility is supplied.
    utilities: Dict[str, Any] = {}
    for k in ("electricity", "water", "sewerage", "broadband"):
        if _alias_present(feats.get(k)):
            v = _alias_display(feats.get(k))
            if v:
                utilities[k] = v
    if utilities:
        out["utilities"] = utilities

    # Obligations: listed, restrictions, access (restrictive covenants etc.)
    obligations = feats.get("obligations")
    if isinstance(obligations, dict):
        for src_key, canon in (
            ("listed", "listed"),
            ("restrictions", "restrictions"),
            ("privateAccess", "access"),
            ("requiredAccess", "access"),
            ("rightsOfWay", "access"),
        ):
            v = obligations.get(src_key)
            # Schema variant 1: {alias: "false"|"true", displayText: "Yes/No"}
            if isinstance(v, dict):
                alias = v.get("alias")
                if isinstance(alias, str):
                    out[canon] = v.get("displayText") or alias
            # Schema variant 2: bool
            elif isinstance(v, bool):
                out[canon] = "Yes" if v else "No"

    # Risks: flood_risk
    risks = feats.get("risks")
    if isinstance(risks, dict):
        for k in ("floodRisk", "floodHistory", "floodDefences"):
            entry = risks.get(k)
            if _alias_present(entry):
                disp = _alias_display(entry)
                if disp and not out.get("flood_risk"):
                    out["flood_risk"] = disp
                    break
        # Schema variant 2: floodSources list / floodedInLastFiveYears bool
        if "flood_risk" not in out:
            sources = risks.get("floodSources")
            in_last_5 = risks.get("floodedInLastFiveYears")
            if isinstance(sources, list) and sources:
                out["flood_risk"] = ", ".join(str(s) for s in sources)
            elif isinstance(in_last_5, bool):
                out["flood_risk"] = "Flooded in last 5 years" if in_last_5 else "Not flooded in last 5 years"

    return out


def _extract_status_availability(data: Dict[str, Any]) -> Optional[str]:
    """
    `status.available` (bool) or `status.published` (bool). Map to a
    short string the validator can count as present.
    """
    status = data.get("status")
    if isinstance(status, dict):
        if status.get("available") is True:
            return "available"
        if status.get("available") is False:
            return "unavailable"
        if status.get("published") is True:
            return "published"
        if status.get("archived") is True:
            return "archived"
        if isinstance(status.get("label"), str):
            return status["label"]
    return None


def _extract_stations(data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """
    Pull nearby train stations from `stations[]` or `nearestStations[]`.
    Returns up to the first 3 with name + distance so the field is
    informative without being verbose.
    """
    for key in ("nearestStations", "stations"):
        stations = data.get(key)
        if isinstance(stations, list) and stations:
            out: List[Dict[str, Any]] = []
            for s in stations[:3]:
                if not isinstance(s, dict):
                    continue
                name = s.get("station") or s.get("name")
                dist = s.get("distance")
                unit = s.get("unit") or "miles"
                if name:
                    entry: Dict[str, Any] = {"name": name}
                    if isinstance(dist, (int, float)):
                        entry["distance"] = round(float(dist), 2)
                        entry["unit"] = unit
                    out.append(entry)
            if out:
                return out
    return None


def _extract_video_urls(data: Dict[str, Any]) -> List[str]:
    """Extract virtualTours[].uri / url — Rightmove serves these as MP4s."""
    urls: List[str] = []
    tours = data.get("virtualTours")
    if isinstance(tours, list):
        for t in tours:
            if isinstance(t, dict):
                u = t.get("uri") or t.get("url")
                if isinstance(u, str) and u.startswith("http"):
                    urls.append(u)
            elif isinstance(t, str) and t.startswith("http"):
                urls.append(t)
    return urls


def _extract_shared_ownership(data: Dict[str, Any]) -> Optional[bool]:
    """
    Read `sharedOwnership.sharedOwnershipFlag` (newer schema) or
    `sharedOwnershipPercentage` non-null (older). Returns False so the
    field is recorded as a real value when the listing is not shared
    ownership — both states are informative.
    """
    so = data.get("sharedOwnership")
    if isinstance(so, dict):
        flag = so.get("sharedOwnershipFlag")
        if isinstance(flag, bool):
            return flag
        if so.get("ownershipPercentage") is not None:
            return True
    sales = data.get("salesInfo")
    if isinstance(sales, dict):
        if sales.get("sharedOwnershipPercentage") is not None:
            return True
    return None


def _extract_epcs(data: Dict[str, Any]) -> List[str]:
    """
    Pull EPC URLs from `epcs[]` or `epcGraphs[]` (both empty lists are
    common — Rightmove only exposes EPC data when the agent uploaded it).
    """
    urls: List[str] = []
    for key in ("epcs", "epcGraphs"):
        items = data.get(key)
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict):
                    u = (
                        it.get("url")
                        or it.get("imageUrl")
                        or it.get("originalUrl")
                    )
                    if isinstance(u, str) and u.startswith("http"):
                        urls.append(u)
                elif isinstance(it, str) and it.startswith("http"):
                    urls.append(it)
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
    video_urls: List[str] = []
    epc_urls: List[str] = []

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

        # Images / floorplans / videos / EPCs (accumulate across blocks;
        # dedupe later).
        image_urls.extend(_extract_image_urls(block))
        floorplan_urls.extend(_extract_floorplan_urls(block))
        video_urls.extend(_extract_video_urls(block))
        epc_urls.extend(_extract_epcs(block))

        # Coordinates
        if not fields.get("address_coordinates"):
            coords = _extract_coordinates(block)
            if coords:
                fields["address_coordinates"] = coords

        # Created date — derived from analyticsInfo.added or listingHistory
        if not fields.get("created_date"):
            cd = _extract_created_date(block)
            if cd:
                fields["created_date"] = cd

        # Tenure (FREEHOLD / LEASEHOLD / SHARE_OF_FREEHOLD …)
        if not fields.get("tenure"):
            tenure = _extract_tenure(block)
            if tenure:
                fields["tenure"] = tenure

        # Size (skip Rightmove's "Ask agent" placeholder)
        if not fields.get("size"):
            size = _extract_size(block)
            if size:
                fields["size"] = size

        # Status availability
        if not fields.get("status_availability"):
            sa = _extract_status_availability(block)
            if sa:
                fields["status_availability"] = sa

        # Train stations nearby
        if not fields.get("train_station_nearby"):
            stations = _extract_stations(block)
            if stations:
                fields["train_station_nearby"] = stations

        # Shared ownership flag (False is informative — record either way)
        if "shared_ownership" not in fields:
            so = _extract_shared_ownership(block)
            if so is not None:
                fields["shared_ownership"] = so

        # Features cluster: garden, parking, accessibility, heating,
        # utilities, listed, restrictions, access, flood_risk
        feats = _extract_features_cluster(block)
        for k, v in feats.items():
            if v not in (None, "", []) and not fields.get(k):
                fields[k] = v

    # Address split — derive road / town from full_address when Rightmove
    # didn't already supply them split. Doesn't overwrite explicit values.
    full_addr = fields.get("full_address")
    if full_addr and (not fields.get("address_road") or not fields.get("address_town")):
        road, town = _split_address(full_addr)
        if road and not fields.get("address_road"):
            fields["address_road"] = road
        if town and not fields.get("address_town"):
            fields["address_town"] = town

    # Dedupe media while preserving order
    image_urls = list(dict.fromkeys(image_urls))
    floorplan_urls = list(dict.fromkeys(floorplan_urls))
    video_urls = list(dict.fromkeys(video_urls))
    epc_urls = list(dict.fromkeys(epc_urls))

    # Surface media into fields too, so the validator's presence check
    # for image_urls / floorplan_urls / video_urls / epcs passes when
    # arrays are non-empty.
    if image_urls and not fields.get("image_urls"):
        fields["image_urls"] = image_urls
    if floorplan_urls and not fields.get("floorplan_urls"):
        fields["floorplan_urls"] = floorplan_urls
    if video_urls and not fields.get("video_urls"):
        fields["video_urls"] = video_urls
    if epc_urls and not fields.get("epcs"):
        fields["epcs"] = epc_urls

    # Default source_url to the URL the caller passed if not already set
    if not fields.get("source_url"):
        fields["source_url"] = source_url

    return fields, image_urls, floorplan_urls
