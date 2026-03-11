"""
Validation Gate — compares adapter output against Firecrawl baseline.

Current implementation: PRESENCE-CHECK ONLY.
Checks Priority 0 fields (images, price, address) that the baseline
detected as present and verifies the adapter also found them.

Future enhancements (documented, not implemented):
- Field-by-field diff (compare actual values, not just presence)
- Content similarity scoring (fuzzy match address strings, etc.)
- Image URL resolution validation (check if high-res URLs actually resolve)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from data_capture_service.adapters.base import BaselineResult, ParsedDataCaptureResult
from data_capture_service.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ValidationCheck:
    """Result of a single validation check."""

    field_name: str
    check_type: str  # "presence"
    baseline_has: bool
    adapter_has: bool
    passed: bool
    message: str


@dataclass
class ValidationResult:
    """Full result from the validation gate."""

    passed: bool
    checks: List[ValidationCheck] = field(default_factory=list)
    summary: str = ""
    baseline_available: bool = False


def validate_against_baseline(
    adapter_parsed: ParsedDataCaptureResult,
    baseline: Optional[BaselineResult],
) -> ValidationResult:
    """
    Validate adapter output against the Firecrawl baseline.

    Presence-check logic (confirmed by user):
    1. If baseline found images and adapter returned none → FAIL
    2. If baseline found price and adapter returned no price → FAIL
    3. If baseline found address and adapter returned no address → FAIL

    Only penalizes MISSING fields that the baseline detected as PRESENT.
    If the baseline itself didn't detect a field, we don't penalize the adapter.

    If baseline is None (Firecrawl failed/disabled), gate is pass-through.
    If validation gate is disabled in config, gate is pass-through.
    """

    # --- Pass-through cases ---
    if not settings.VALIDATION_GATE_ENABLED:
        logger.info("Validation gate disabled — passing through")
        return ValidationResult(
            passed=True,
            summary="Validation gate disabled",
            baseline_available=False,
        )

    if baseline is None:
        logger.info("No baseline available — passing through")
        return ValidationResult(
            passed=True,
            summary="No baseline available (Firecrawl disabled or failed)",
            baseline_available=False,
        )

    if baseline.status != "success":
        logger.info(f"Baseline status is {baseline.status} — passing through")
        return ValidationResult(
            passed=True,
            summary=f"Baseline not successful (status={baseline.status})",
            baseline_available=False,
        )

    # --- Run presence checks on Priority 0 fields ---
    checks: List[ValidationCheck] = []
    all_passed = True

    # Check 1: Images
    baseline_has_images = baseline.image_count > 0
    adapter_has_images = len(adapter_parsed.image_urls) > 0
    image_check = ValidationCheck(
        field_name="image_urls",
        check_type="presence",
        baseline_has=baseline_has_images,
        adapter_has=adapter_has_images,
        passed=not baseline_has_images or adapter_has_images,
        message=(
            f"Baseline found {baseline.image_count} images, "
            f"adapter found {len(adapter_parsed.image_urls)}"
        ),
    )
    checks.append(image_check)
    if not image_check.passed:
        all_passed = False
        logger.warning(
            f"Validation FAIL: Baseline found {baseline.image_count} images "
            f"but adapter returned none"
        )

    # Check 2: Price
    baseline_has_price = baseline.has_price
    adapter_has_price = adapter_parsed.field_presence.get("price", False)
    price_check = ValidationCheck(
        field_name="price",
        check_type="presence",
        baseline_has=baseline_has_price,
        adapter_has=adapter_has_price,
        passed=not baseline_has_price or adapter_has_price,
        message=(
            f"Baseline has_price={baseline_has_price}, "
            f"adapter has_price={adapter_has_price}"
        ),
    )
    checks.append(price_check)
    if not price_check.passed:
        all_passed = False
        logger.warning("Validation FAIL: Baseline found price but adapter did not")

    # Check 3: Address
    baseline_has_address = baseline.has_address
    adapter_has_address = adapter_parsed.field_presence.get("address_road", False)
    address_check = ValidationCheck(
        field_name="address_road",
        check_type="presence",
        baseline_has=baseline_has_address,
        adapter_has=adapter_has_address,
        passed=not baseline_has_address or adapter_has_address,
        message=(
            f"Baseline has_address={baseline_has_address}, "
            f"adapter has_address={adapter_has_address}"
        ),
    )
    checks.append(address_check)
    if not address_check.passed:
        all_passed = False
        logger.warning("Validation FAIL: Baseline found address but adapter did not")

    # Build summary
    failed_checks = [c for c in checks if not c.passed]
    if all_passed:
        summary = f"All {len(checks)} presence checks passed"
    else:
        failed_names = [c.field_name for c in failed_checks]
        summary = (
            f"{len(failed_checks)}/{len(checks)} checks failed: "
            f"missing {', '.join(failed_names)}"
        )

    logger.info(f"Validation gate result: passed={all_passed}, {summary}")

    return ValidationResult(
        passed=all_passed,
        checks=checks,
        summary=summary,
        baseline_available=True,
    )
