"""
Parser registry — maps an adapter name to a payload parser.

The /fetchers/validate primitive lets callers pass either pre-extracted
`fields` OR a `raw_payload` they want the service to parse. The previous
implementation hardcoded the Motie parser for ANY raw_payload (rule 3
violation: Motie was implicitly "the" parser). This registry lets us pick
the right parser per adapter without touching the router.

Today we ship the Motie and Firecrawl parsers. Adding a new vendor parser
is registering it here; no router changes.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from data_capture_service.adapters.motie.motie_parser import parse_motie_result
from data_capture_service.services.baseline_provider import (
    parse_markdown_for_field_presence,
)

logger = logging.getLogger(__name__)


# A parser takes (raw_payload_dict, source_url) and returns
# (fields_dict, image_urls, floorplan_urls). For adapters that don't extract
# media URLs, image_urls/floorplan_urls can be empty lists.
ParserFn = Callable[[Dict[str, Any], str], Tuple[Dict[str, Any], List[str], List[str]]]


def _firecrawl_parser(
    raw_payload: Dict[str, Any], source_url: str
) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """
    Parse Firecrawl-shaped raw payload (markdown + presence map) into the
    canonical field dict that /fetchers/validate expects.

    Firecrawl is a presence-only parser in MVP (rule from docs: "(a) baseline
    expectations" — schema + essential data). Field values are present-or-not
    booleans, not extracted strings.
    """
    presence: Dict[str, Any] = {}
    if isinstance(raw_payload.get("field_presence"), dict):
        presence = dict(raw_payload["field_presence"])
    elif isinstance(raw_payload.get("markdown"), str):
        presence = parse_markdown_for_field_presence(raw_payload["markdown"]) or {}
    presence.pop("_image_count", None)

    fields: Dict[str, Any] = {k: True if v else None for k, v in presence.items()}
    if not fields.get("source_url"):
        fields["source_url"] = source_url
    return fields, [], []


_PARSERS: Dict[str, ParserFn] = {
    "motie": parse_motie_result,
    "firecrawl": _firecrawl_parser,
}


def register(adapter_name: str, parser: ParserFn) -> None:
    """Register a parser for an adapter (call at module import time)."""
    _PARSERS[adapter_name] = parser


def get(adapter_name: str) -> Optional[ParserFn]:
    """Return the parser for an adapter name, or None if unregistered."""
    return _PARSERS.get(adapter_name)


def known() -> List[str]:
    return sorted(_PARSERS.keys())
