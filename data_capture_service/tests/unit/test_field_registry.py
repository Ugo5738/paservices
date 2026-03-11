"""
Tests for the field registry and completeness scoring.
"""

import pytest

from data_capture_service.services.field_registry import (
    ALL_FIELDS,
    FIELD_PRIORITIES,
    PRIORITY_WEIGHTS,
    compute_completeness_score,
    compute_field_presence,
)


class TestComputeFieldPresence:
    """Test field presence detection."""

    def test_all_fields_present(self):
        """All fields with values should be detected as present."""
        fields = {f: "some_value" for f in ALL_FIELDS}
        presence = compute_field_presence(fields)
        assert all(presence.values())
        assert len(presence) == len(ALL_FIELDS)

    def test_no_fields_present(self):
        """Empty dict should result in all False."""
        presence = compute_field_presence({})
        assert not any(presence.values())

    def test_null_values_not_present(self):
        """None, 'null', 'none', 'n/a', and empty strings should be False."""
        fields = {
            "price": None,
            "address_road": "null",
            "bedrooms": "none",
            "bathrooms": "n/a",
            "description": "",
        }
        presence = compute_field_presence(fields)
        assert not presence["price"]
        assert not presence["address_road"]
        assert not presence["bedrooms"]
        assert not presence["bathrooms"]
        assert not presence["description"]

    def test_empty_lists_not_present(self):
        """Empty lists should be False."""
        fields = {"image_urls": [], "floorplan_urls": []}
        presence = compute_field_presence(fields)
        assert not presence["image_urls"]
        assert not presence["floorplan_urls"]

    def test_populated_lists_present(self):
        """Non-empty lists should be True."""
        fields = {
            "image_urls": ["http://example.com/img.jpg"],
            "floorplan_urls": ["http://example.com/fp.jpg"],
        }
        presence = compute_field_presence(fields)
        assert presence["image_urls"]
        assert presence["floorplan_urls"]

    def test_numeric_values_present(self):
        """Numeric values (including 0) should be True."""
        fields = {"bedrooms": 0, "bathrooms": 3}
        presence = compute_field_presence(fields)
        assert presence["bedrooms"]
        assert presence["bathrooms"]


class TestComputeCompletenessScore:
    """Test completeness scoring logic."""

    def test_perfect_score(self):
        """All fields present should give score close to 1.0."""
        presence = {f: True for f in ALL_FIELDS}
        score = compute_completeness_score(presence)
        assert score.overall == 1.0
        assert score.fields_present == len(ALL_FIELDS)
        assert score.fields_total == len(ALL_FIELDS)

    def test_zero_score(self):
        """No fields present should give score of 0.0."""
        presence = {f: False for f in ALL_FIELDS}
        score = compute_completeness_score(presence)
        assert score.overall == 0.0
        assert score.fields_present == 0

    def test_only_p0_fields(self):
        """Only Priority 0 fields should give high score due to high weight."""
        presence = {f: False for f in ALL_FIELDS}
        for f in FIELD_PRIORITIES[0]:
            presence[f] = True

        score = compute_completeness_score(presence)
        # P0 has weight 1.0, so it should contribute significantly
        assert score.overall > 0.3
        assert score.priority_scores[0] == 1.0
        assert score.priority_scores[1] == 0.0

    def test_missing_p0_fields_tracked(self):
        """Missing P0 fields should be listed in details."""
        presence = {f: False for f in ALL_FIELDS}
        presence["price"] = True  # Only one P0 field

        score = compute_completeness_score(presence)
        missing_p0 = score.details["missing_p0"]
        assert "address_road" in missing_p0
        assert "image_urls" in missing_p0
        assert "price" not in missing_p0

    def test_priority_weights_applied(self):
        """Higher priority fields should contribute more to the score."""
        # Only P0 fields
        presence_p0 = {f: False for f in ALL_FIELDS}
        for f in FIELD_PRIORITIES[0]:
            presence_p0[f] = True
        score_p0 = compute_completeness_score(presence_p0)

        # Only P5 fields
        presence_p5 = {f: False for f in ALL_FIELDS}
        for f in FIELD_PRIORITIES[5]:
            presence_p5[f] = True
        score_p5 = compute_completeness_score(presence_p5)

        # P0-only should score higher than P5-only
        assert score_p0.overall > score_p5.overall

    def test_per_tier_scores(self):
        """Each tier should have its own score."""
        presence = {f: False for f in ALL_FIELDS}
        # Fill half of P1 fields
        p1_fields = FIELD_PRIORITIES[1]
        for f in p1_fields[:len(p1_fields) // 2]:
            presence[f] = True

        score = compute_completeness_score(presence)
        assert 0 < score.priority_scores[1] < 1.0

    def test_empty_presence_dict(self):
        """Empty presence dict should still work."""
        score = compute_completeness_score({})
        assert score.overall == 0.0
