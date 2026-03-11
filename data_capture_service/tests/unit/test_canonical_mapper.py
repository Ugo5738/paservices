"""
Tests for canonical mapper — field mapping to columns and extras.
"""

import pytest

from data_capture_service.adapters.base import AdapterStatus, ParsedDataCaptureResult
from data_capture_service.mappers.canonical_mapper import map_to_canonical


class TestCanonicalMapper:
    """Test mapping from parsed result to canonical format."""

    def _make_parsed(self, fields=None, image_urls=None, floorplan_urls=None):
        return ParsedDataCaptureResult(
            adapter_name="motie",
            url="http://example.com/prop/123",
            status=AdapterStatus.SUCCESS,
            fields=fields or {},
            image_urls=image_urls or [],
            floorplan_urls=floorplan_urls or [],
        )

    def test_priority_0_3_to_columns(self):
        """Priority 0-3 fields should map to column_fields."""
        parsed = self._make_parsed(
            fields={
                "address_road": "123 High Street",
                "price": "£350,000",
                "address_town": "London",
                "bedrooms": 3,
                "postcode": "SW1A 1AA",
                "description": "A lovely home",
            }
        )

        columns, extras, media = map_to_canonical(parsed, "http://example.com", "motie")

        assert columns["address_road"] == "123 High Street"
        assert columns["price"] == "£350,000"
        assert columns["address_town"] == "London"
        assert columns["bedrooms"] == 3
        assert columns["postcode"] == "SW1A 1AA"
        assert columns["description"] == "A lovely home"

    def test_priority_4_plus_to_extras(self):
        """Priority 4+ fields should go to extras_json."""
        parsed = self._make_parsed(
            fields={
                "tenure": "freehold",
                "garden": "Large garden",
                "parking": "Double garage",
                "flood_risk": "Low",
            }
        )

        columns, extras, media = map_to_canonical(parsed, "http://example.com", "motie")

        assert "tenure" not in columns
        assert extras["tenure"] == "freehold"
        assert extras["garden"] == "Large garden"
        assert extras["parking"] == "Double garage"
        assert extras["flood_risk"] == "Low"

    def test_images_to_media(self):
        """Image URLs should become photo media items."""
        parsed = self._make_parsed(
            image_urls=["http://img1.jpg", "http://img2.jpg"]
        )

        _, _, media = map_to_canonical(parsed, "http://example.com", "motie")

        assert len(media) == 2
        assert media[0]["media_type"] == "photo"
        assert media[0]["url"] == "http://img1.jpg"
        assert media[0]["sort_order"] == 0
        assert media[1]["sort_order"] == 1

    def test_floorplans_to_media(self):
        """Floorplan URLs should become floorplan media items."""
        parsed = self._make_parsed(
            floorplan_urls=["http://fp1.jpg"]
        )

        _, _, media = map_to_canonical(parsed, "http://example.com", "motie")

        assert len(media) == 1
        assert media[0]["media_type"] == "floorplan"

    def test_high_res_detection(self):
        """High-res URLs should be flagged."""
        parsed = self._make_parsed(
            image_urls=[
                "http://example.com/1024/768/photo.jpg",
                "http://example.com/small/photo.jpg",
            ]
        )

        _, _, media = map_to_canonical(parsed, "http://example.com", "motie")

        assert media[0]["is_high_res"] is True
        assert media[1]["is_high_res"] is False

    def test_none_values_excluded(self):
        """None values should not appear in column_fields or extras."""
        parsed = self._make_parsed(
            fields={"price": "£100", "address_road": None}
        )

        columns, extras, _ = map_to_canonical(parsed, "http://example.com", "motie")

        assert "price" in columns
        assert "address_road" not in columns

    def test_empty_parsed(self):
        """Empty parsed result should not crash."""
        parsed = self._make_parsed()
        columns, extras, media = map_to_canonical(parsed, "http://example.com", "motie")

        assert isinstance(columns, dict)
        assert isinstance(extras, dict)
        assert isinstance(media, list)

    def test_video_urls_to_media(self):
        """Video URLs should become video media items."""
        parsed = self._make_parsed(
            fields={
                "video_urls": [
                    "http://example.com/video1.mp4",
                    "http://example.com/video2.mp4",
                ]
            }
        )

        _, _, media = map_to_canonical(parsed, "http://example.com", "motie")

        video_items = [m for m in media if m["media_type"] == "video"]
        assert len(video_items) == 2
