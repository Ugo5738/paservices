"""
Tests for the url_parsing utility module.
"""
import pytest

from data_capture_rightmove_service.utils.url_parsing import (
    extract_rightmove_property_id,
    is_valid_rightmove_url,
    determine_rightmove_api_endpoints,
)


class TestRightmoveUrlParsing:
    """Test suite for Rightmove URL parsing functions."""

    @pytest.mark.parametrize(
        "url,expected_id",
        [
            # Valid URLs with IDs
            ("https://www.rightmove.co.uk/properties/154508327", 154508327),
            ("https://www.rightmove.co.uk/properties/154508327#/?channel=RES_LET", 154508327),
            ("https://www.rightmove.co.uk/properties/123456789?param=value", 123456789),
            ("http://rightmove.co.uk/properties/123", 123),
            # Invalid URLs or no ID
            (None, None),
            ("", None),
            ("https://www.example.com", None),
            ("https://www.rightmove.co.uk/for-sale/property-12345.html", None),
            ("https://www.rightmove.co.uk/properties/", None),
            ("https://www.rightmove.co.uk/properties/invalid", None),
        ],
    )
    def test_extract_rightmove_property_id(self, url, expected_id):
        """Test extracting property IDs from various URLs."""
        assert extract_rightmove_property_id(url) == expected_id

    @pytest.mark.parametrize(
        "url,expected_result",
        [
            # Valid URLs
            ("https://www.rightmove.co.uk/properties/154508327", True),
            ("https://www.rightmove.co.uk/properties/154508327#/?channel=RES_LET", True),
            ("http://rightmove.co.uk/properties/123", True),
            # Invalid URLs
            (None, False),
            ("", False),
            ("https://www.example.com", False),
            ("https://www.rightmove.co.uk/for-sale/property-12345.html", False),
            ("https://www.rightmove.co.uk/properties/", False),
            ("https://www.rightmove.co.uk/properties/invalid", False),
        ],
    )
    def test_is_valid_rightmove_url(self, url, expected_result):
        """Test validating Rightmove property URLs."""
        assert is_valid_rightmove_url(url) == expected_result

    @pytest.mark.parametrize(
        "url,expected_primary,expected_secondary",
        [
            # For-sale URLs should prioritize property-for-sale endpoint
            (
                "https://www.rightmove.co.uk/property-for-sale/property-123456789.html",
                "property_for_sale",
                "properties_details",
            ),
            (
                "https://www.rightmove.co.uk/properties/123456789#/?channel=for-sale",
                "property_for_sale", 
                "properties_details"
            ),
            # Regular property URLs should prioritize properties_details endpoint
            (
                "https://www.rightmove.co.uk/properties/123456789",
                "properties_details",
                "property_for_sale",
            ),
            (None, "properties_details", "property_for_sale"),
        ],
    )
    def test_determine_rightmove_api_endpoints(self, url, expected_primary, expected_secondary):
        """Test determining which API endpoints to use based on URL structure."""
        primary, secondary = determine_rightmove_api_endpoints(url)
        assert primary == expected_primary
        assert secondary == expected_secondary
