"""
Tests for Motie result parser — variable JSON output parsing.
"""

import pytest

from data_capture_service.adapters.motie.motie_parser import parse_motie_result


class TestMotieParser:
    """Test parsing of Motie's variable JSON output."""

    def test_standard_output(self):
        """Parse a standard Motie output with expected keys."""
        data = {
            "address_road_name": "123 High Street",
            "price": "£350,000",
            "bedrooms_number": 3,
            "bathrooms_number": 2,
            "type": "Detached House",
            "estate_agent_name": "Test Agent",
            "estate_agent_address": "1 Agent Road, London",
            "address_town": "London",
            "address_postcode": "SW1A 1AA",
            "description_full": "A lovely property...",
            "address_full": "123 High Street, London SW1A 1AA",
            "image_urls": [
                {"url": "http://img1.jpg"},
                {"url": "http://img2.jpg"},
            ],
            "floorplan_images_urls": [
                {"url": "http://fp1.jpg"},
            ],
        }

        fields, images, floorplans = parse_motie_result(data, "http://example.com")

        assert fields["address_road"] == "123 High Street"
        assert fields["price"] == "£350,000"
        assert fields["bedrooms"] == 3
        assert fields["bathrooms"] == 2
        assert fields["property_type"] == "Detached House"
        assert fields["estate_agent_name"] == "Test Agent"
        assert fields["postcode"] == "SW1A 1AA"
        assert len(images) == 2
        assert len(floorplans) == 1

    def test_nested_data_key(self):
        """Parse when Motie wraps result in a 'data' key."""
        data = {
            "data": {
                "address_road_name": "456 Oak Avenue",
                "price": "£200,000",
                "bedrooms_number": 2,
            }
        }

        fields, _, _ = parse_motie_result(data, "http://example.com")
        assert fields["address_road"] == "456 Oak Avenue"
        assert fields["price"] == "£200,000"
        assert fields["bedrooms"] == 2

    def test_null_string_values(self):
        """Null strings should be treated as None."""
        data = {
            "address_road_name": "Test Road",
            "tenure": "null",
            "garden": "None",
            "parking": "n/a",
        }

        fields, _, _ = parse_motie_result(data, "http://example.com")
        assert fields["address_road"] == "Test Road"
        assert fields.get("tenure") is None
        assert fields.get("garden") is None
        assert fields.get("parking") is None

    def test_image_urls_as_strings(self):
        """Parse image URLs provided as plain strings."""
        data = {
            "image_urls": [
                "http://img1.jpg",
                "http://img2.jpg",
            ]
        }

        _, images, _ = parse_motie_result(data, "http://example.com")
        assert len(images) == 2
        assert images[0] == "http://img1.jpg"

    def test_image_urls_as_dicts(self):
        """Parse image URLs provided as dicts with 'url' key."""
        data = {
            "image_urls": [
                {"url": "http://img1.jpg"},
                {"url": "http://img2.jpg"},
            ]
        }

        _, images, _ = parse_motie_result(data, "http://example.com")
        assert len(images) == 2

    def test_bedrooms_as_float(self):
        """Parse bedrooms when provided as float (from Motie)."""
        data = {"bedrooms_number": 4.0}
        fields, _, _ = parse_motie_result(data, "http://example.com")
        assert fields["bedrooms"] == 4

    def test_bedrooms_as_string(self):
        """Parse bedrooms when provided as string."""
        data = {"bedrooms_number": "3 bedrooms"}
        fields, _, _ = parse_motie_result(data, "http://example.com")
        assert fields["bedrooms"] == 3

    def test_source_url_fallback(self):
        """Source URL should fall back to the provided URL."""
        data = {}
        fields, _, _ = parse_motie_result(data, "http://example.com/prop/123")
        assert fields["source_url"] == "http://example.com/prop/123"

    def test_empty_data(self):
        """Empty data should not crash."""
        fields, images, floorplans = parse_motie_result({}, "http://example.com")
        assert isinstance(fields, dict)
        assert isinstance(images, list)
        assert isinstance(floorplans, list)

    def test_alternative_field_names(self):
        """Parser should handle alternative key names."""
        data = {
            "road": "Test Road",
            "beds": "4",
            "baths": "2",
            "marketed_by": "Agent X",
        }

        fields, _, _ = parse_motie_result(data, "http://example.com")
        assert fields["address_road"] == "Test Road"
        assert fields["bedrooms"] == 4
        assert fields["bathrooms"] == 2
        assert fields["estate_agent_name"] == "Agent X"
