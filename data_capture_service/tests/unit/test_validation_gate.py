"""
Tests for the validation gate — all pass/fail combinations.
"""

import pytest

from data_capture_service.adapters.base import AdapterStatus, BaselineResult, ParsedDataCaptureResult
from data_capture_service.services.validation_gate import validate_against_baseline


class TestValidationGate:
    """Test validation gate presence-check logic."""

    def _make_baseline(
        self,
        has_price=True,
        has_address=True,
        image_count=5,
        has_floorplan=False,
        status=AdapterStatus.SUCCESS,
    ) -> BaselineResult:
        return BaselineResult(
            url="https://example.com/property/123",
            status=status,
            has_price=has_price,
            has_address=has_address,
            image_count=image_count,
            has_floorplan=has_floorplan,
            field_presence={
                "price": has_price,
                "address_road": has_address,
                "image_urls": image_count > 0,
            },
        )

    def _make_parsed(
        self,
        has_price=True,
        has_address=True,
        image_urls=None,
    ) -> ParsedDataCaptureResult:
        if image_urls is None:
            image_urls = ["http://img1.jpg", "http://img2.jpg"]

        return ParsedDataCaptureResult(
            adapter_name="motie",
            url="https://example.com/property/123",
            status=AdapterStatus.SUCCESS,
            field_presence={
                "price": has_price,
                "address_road": has_address,
            },
            image_urls=image_urls,
        )

    def test_all_present_passes(self):
        """Baseline and adapter both have everything → PASS."""
        baseline = self._make_baseline()
        parsed = self._make_parsed()
        result = validate_against_baseline(parsed, baseline)
        assert result.passed
        assert result.baseline_available
        assert len(result.checks) == 3

    def test_baseline_has_images_adapter_missing_fails(self):
        """Baseline found images but adapter returned none → FAIL."""
        baseline = self._make_baseline(image_count=10)
        parsed = self._make_parsed(image_urls=[])
        result = validate_against_baseline(parsed, baseline)
        assert not result.passed
        failed = [c for c in result.checks if not c.passed]
        assert any(c.field_name == "image_urls" for c in failed)

    def test_baseline_has_price_adapter_missing_fails(self):
        """Baseline found price but adapter returned no price → FAIL."""
        baseline = self._make_baseline(has_price=True)
        parsed = self._make_parsed(has_price=False)
        result = validate_against_baseline(parsed, baseline)
        assert not result.passed
        failed = [c for c in result.checks if not c.passed]
        assert any(c.field_name == "price" for c in failed)

    def test_baseline_has_address_adapter_missing_fails(self):
        """Baseline found address but adapter returned no address → FAIL."""
        baseline = self._make_baseline(has_address=True)
        parsed = self._make_parsed(has_address=False)
        result = validate_against_baseline(parsed, baseline)
        assert not result.passed
        failed = [c for c in result.checks if not c.passed]
        assert any(c.field_name == "address_road" for c in failed)

    def test_baseline_missing_field_adapter_also_missing_passes(self):
        """If baseline didn't find a field, adapter isn't penalized."""
        baseline = self._make_baseline(has_price=False, image_count=0)
        parsed = self._make_parsed(has_price=False, image_urls=[])
        result = validate_against_baseline(parsed, baseline)
        assert result.passed

    def test_no_baseline_passes_through(self):
        """If baseline is None, gate is pass-through."""
        parsed = self._make_parsed()
        result = validate_against_baseline(parsed, None)
        assert result.passed
        assert not result.baseline_available

    def test_failed_baseline_passes_through(self):
        """If baseline failed, gate is pass-through."""
        baseline = self._make_baseline(status=AdapterStatus.FAILED)
        parsed = self._make_parsed()
        result = validate_against_baseline(parsed, baseline)
        assert result.passed

    def test_multiple_failures(self):
        """Multiple missing fields should all be reported."""
        baseline = self._make_baseline(has_price=True, has_address=True, image_count=5)
        parsed = self._make_parsed(has_price=False, has_address=False, image_urls=[])
        result = validate_against_baseline(parsed, baseline)
        assert not result.passed
        failed = [c for c in result.checks if not c.passed]
        assert len(failed) == 3  # images, price, and address

    def test_summary_message(self):
        """Summary should describe what failed."""
        baseline = self._make_baseline(has_price=True)
        parsed = self._make_parsed(has_price=False)
        result = validate_against_baseline(parsed, baseline)
        assert "price" in result.summary
