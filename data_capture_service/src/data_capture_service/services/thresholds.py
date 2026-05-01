"""
Service-owned thresholds for V2 data-capture primitives.

Per Daniel's Apr 2026 alignment with Rolf: thresholds live in the service as
hardcoded constants — NOT as env vars, NOT in n8n workflow JSON. They can be
changed by editing this module and redeploying. Putting them here (rather
than per-fetcher in the DB) keeps the model explicit and trivial to find.

The completeness scoring itself is tier-weighted (P0 = 1.0, P1 = 0.8, ...,
P5 = 0.1) — see services.field_registry. So a "0.85" threshold means "the
weighted score across all priority tiers must be >= 0.85", which a missing
low-priority field will not flunk by itself.
"""

# /fetchers/validate "passed" cutoff. The tier-weighted completeness score
# from field_registry must meet or exceed this for the validation primitive
# to return passed=true. Mirrors the legacy COMPLETENESS_ACCEPT_THRESHOLD.
VALIDATE_PASS_THRESHOLD: float = 0.85

# W3 build-loop "good enough to publish" score. A build whose Motie output
# matches the AI-fetcher baseline at this threshold or above gets published
# without further repair iterations.
BUILD_PUBLISH_THRESHOLD: float = 0.85

# W3 build-loop max repair attempts. After this many tries, MVP behaviour:
# publish the best attempt regardless of score (don't hard-gate). Future
# behaviour may switch to "fail the build flag" instead.
BUILD_MAX_REPAIR_ATTEMPTS: int = 3

# WF B (AI-fetcher multishot) "good enough" cutoff. If an AI-fetcher run
# scores at or above this, WF B accepts it without further attempts. The
# threshold is enforced via /fetchers/validate (passed=true), so n8n never
# sees a numeric cutoff in workflow JSON.
AI_FETCHER_GOOD_ENOUGH_THRESHOLD: float = 0.85
