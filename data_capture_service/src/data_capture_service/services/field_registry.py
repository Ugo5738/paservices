"""
Field Registry — Priority-tiered field specification for property data.

Defines the canonical field set, priority levels, and scoring logic.
Based on the user's spreadsheet defining Priority 0 (Essential) through Priority 5 (Very Low).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from data_capture_service.adapters.base import CompletenessScore

# --- Priority Tiers ---
# Priority 0 = Essential (must have)
# Priority 1 = Very High
# Priority 2 = High
# Priority 3 = Medium
# Priority 4 = Low
# Priority 5 = Very Low

FIELD_PRIORITIES: Dict[int, List[str]] = {
    0: [
        "address_road",
        "floorplan_urls",
        "image_urls",
        "source_url",
        "price",
    ],
    1: [
        "address_town",
        "bedrooms",
        "estate_agent_name",
    ],
    2: [
        "agent_address",
        "transaction_type",
        "bathrooms",
        "property_type",
    ],
    3: [
        "created_date",
        "full_address",
        "postcode",
        "description",
        "rightmove_url",
    ],
    4: [
        "description_short",
        "size",
        "tenure",
        "garden",
        "parking",
        "address_coordinates",
        "status_availability",
        "last_update_reason",
        "epcs",
        "train_station_nearby",
        "video_urls",
    ],
    5: [
        "access",
        "accessibility",
        "flood_risk",
        "heating",
        "listed",
        "restrictions",
        "shared_ownership",
        "utilities",
    ],
}

# Weights applied to each priority tier when computing the overall score
PRIORITY_WEIGHTS: Dict[int, float] = {
    0: 1.0,
    1: 0.8,
    2: 0.6,
    3: 0.4,
    4: 0.2,
    5: 0.1,
}

# Build reverse lookup: field_name -> priority
FIELD_TO_PRIORITY: Dict[str, int] = {}
for priority, fields in FIELD_PRIORITIES.items():
    for f in fields:
        FIELD_TO_PRIORITY[f] = priority

# All known field names
ALL_FIELDS: Set[str] = set(FIELD_TO_PRIORITY.keys())

# Fields that map to real columns on CanonicalPropertySnapshot (Priority 0-3)
CANONICAL_COLUMN_FIELDS: Set[str] = set()
for p in range(4):
    CANONICAL_COLUMN_FIELDS.update(FIELD_PRIORITIES[p])

# Fields stored in extras_json (Priority 4+)
EXTRAS_FIELDS: Set[str] = set()
for p in range(4, 6):
    EXTRAS_FIELDS.update(FIELD_PRIORITIES[p])


def _has_value(value: Any) -> bool:
    """Check if a field value is meaningfully present (not None, empty, or 'null')."""
    if value is None:
        return False
    if isinstance(value, str):
        stripped = value.strip().lower()
        return stripped not in ("", "null", "none", "n/a")
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def compute_field_presence(fields: Dict[str, Any]) -> Dict[str, bool]:
    """
    Given a dict of field_name -> value, return a dict of field_name -> bool
    indicating whether each known field has a meaningful value.
    """
    presence: Dict[str, bool] = {}
    for field_name in ALL_FIELDS:
        presence[field_name] = _has_value(fields.get(field_name))
    return presence


def compute_completeness_score(
    field_presence: Dict[str, bool],
) -> CompletenessScore:
    """
    Compute a weighted completeness score based on field presence and priority tiers.

    Returns a CompletenessScore with:
    - overall: weighted average across all tiers (0.0 to 1.0)
    - priority_scores: per-tier scores
    - fields_present / fields_total: raw counts
    """
    priority_scores: Dict[int, float] = {}
    total_weighted = 0.0
    total_weight = 0.0
    fields_present = 0
    fields_total = 0

    for priority, field_names in FIELD_PRIORITIES.items():
        if not field_names:
            continue

        tier_present = sum(
            1 for f in field_names if field_presence.get(f, False)
        )
        tier_total = len(field_names)
        tier_score = tier_present / tier_total if tier_total > 0 else 0.0

        priority_scores[priority] = round(tier_score, 4)
        weight = PRIORITY_WEIGHTS.get(priority, 0.1)
        total_weighted += tier_score * weight
        total_weight += weight

        fields_present += tier_present
        fields_total += tier_total

    overall = total_weighted / total_weight if total_weight > 0 else 0.0

    return CompletenessScore(
        overall=round(overall, 4),
        priority_scores=priority_scores,
        fields_present=fields_present,
        fields_total=fields_total,
        details={
            "weights": PRIORITY_WEIGHTS,
            "missing_p0": [
                f
                for f in FIELD_PRIORITIES[0]
                if not field_presence.get(f, False)
            ],
        },
    )
