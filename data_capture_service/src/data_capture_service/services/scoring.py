"""
Scoring service — Motie-vs-AI-fetcher scoring + diff for W3's repair loop.

W3 (Motie build) runs the freshly-deployed coded scraper against the same URL
that the AI fetcher (Firecrawl today, AI Council tomorrow) was used on, then
compares the two outputs. The "score" is the tier-weighted completeness of the
Motie output relative to what the AI fetcher confirmed is present on the page.

The MVP behaviour Daniel agreed with Rolf:
  - Score is ALWAYS computed and stored (drift reference).
  - Repair loop runs up to BUILD_MAX_REPAIR_ATTEMPTS attempts.
  - If the loop exhausts without hitting BUILD_PUBLISH_THRESHOLD, publish
    anyway with the final score (don't hard-gate).

Vendor-agnosticism: this module never imports a specific AI fetcher. It takes
parsed-field dicts as input and computes the score; the caller resolves the
"baseline" via ai_fetcher_registry.load_default_baseline.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from data_capture_service.services.field_registry import (
    FIELD_PRIORITIES,
    PRIORITY_WEIGHTS,
    compute_completeness_score,
    compute_field_presence,
)


@dataclass
class ScoringDiff:
    """Per-field diff between baseline (AI fetcher) and candidate (Motie)."""

    # Fields the baseline says ARE present but the candidate is missing.
    # These are the actionable items for a repair prompt.
    missing_in_candidate: List[str] = field(default_factory=list)
    # Fields the candidate has but the baseline did not detect (informational).
    extra_in_candidate: List[str] = field(default_factory=list)
    # Fields present in both — the candidate is doing the right thing for these.
    matched: List[str] = field(default_factory=list)


@dataclass
class ScoringResult:
    """Output of score_against_baseline."""

    candidate_score: float  # tier-weighted completeness of the candidate
    baseline_score: float  # tier-weighted completeness of the baseline
    relative_score: float  # candidate / baseline (capped at 1.0); 0 if baseline empty
    diff: ScoringDiff = field(default_factory=ScoringDiff)
    candidate_priority_scores: Dict[int, float] = field(default_factory=dict)
    baseline_priority_scores: Dict[int, float] = field(default_factory=dict)
    # Convenience: missing P0/P1 fields the repair prompt should call out first.
    missing_critical_in_candidate: List[str] = field(default_factory=list)


def score_against_baseline(
    candidate_fields: Dict[str, Any],
    baseline_fields: Dict[str, Any],
) -> ScoringResult:
    """
    Score a candidate fetcher output against an AI-fetcher baseline.

    Both inputs are dicts of canonical-field -> value (or presence boolean).
    Uses the field-registry presence + tier-weighted scoring under the hood,
    then derives a diff for repair-prompt feedback.
    """
    candidate_presence = compute_field_presence(candidate_fields)
    baseline_presence = compute_field_presence(baseline_fields)

    candidate_score = compute_completeness_score(candidate_presence)
    baseline_score = compute_completeness_score(baseline_presence)

    diff = ScoringDiff()
    for priority, names in FIELD_PRIORITIES.items():
        for name in names:
            in_baseline = baseline_presence.get(name, False)
            in_candidate = candidate_presence.get(name, False)
            if in_baseline and in_candidate:
                diff.matched.append(name)
            elif in_baseline and not in_candidate:
                diff.missing_in_candidate.append(name)
            elif not in_baseline and in_candidate:
                diff.extra_in_candidate.append(name)

    # Critical-tier (P0/P1) misses surface separately so the repair prompt
    # can lead with them.
    missing_critical: List[str] = []
    for priority in (0, 1):
        for name in FIELD_PRIORITIES[priority]:
            if (
                baseline_presence.get(name, False)
                and not candidate_presence.get(name, False)
            ):
                missing_critical.append(name)

    if baseline_score.overall > 0:
        relative = candidate_score.overall / baseline_score.overall
        relative = min(1.0, relative)
    else:
        # Baseline detected nothing — treat candidate score as the absolute
        # measure rather than dividing by zero. This shouldn't happen in
        # practice for property URLs but guards the math.
        relative = candidate_score.overall

    return ScoringResult(
        candidate_score=candidate_score.overall,
        baseline_score=baseline_score.overall,
        relative_score=round(relative, 4),
        diff=diff,
        candidate_priority_scores=candidate_score.priority_scores,
        baseline_priority_scores=baseline_score.priority_scores,
        missing_critical_in_candidate=missing_critical,
    )


def diff_to_repair_payload(diff: ScoringDiff) -> Dict[str, Any]:
    """
    Shape the diff into the dict the repair prompt builder consumes.

    Kept as a helper here so callers don't reach into the dataclass — keeps
    motie_prompts free of scoring-internal types.
    """
    return {
        "missing_fields": list(diff.missing_in_candidate),
        "missing_critical_fields": [
            f for f in diff.missing_in_candidate if f in _CRITICAL_FIELDS
        ],
    }


_CRITICAL_FIELDS: List[str] = []
for _p in (0, 1):
    _CRITICAL_FIELDS.extend(FIELD_PRIORITIES[_p])
