"""
Tests for Firecrawl baseline provider — markdown field presence parsing.
"""

import pytest

from data_capture_service.services.baseline_provider import parse_markdown_for_field_presence


class TestParseMarkdownForFieldPresence:
    """Test regex-based field detection from markdown."""

    def test_price_detection_gbp(self):
        """Detect GBP prices like £350,000."""
        markdown = "This property is listed for £350,000."
        presence = parse_markdown_for_field_presence(markdown)
        assert presence["price"] is True

    def test_price_detection_missing(self):
        """No price pattern should return False."""
        markdown = "A lovely detached house with 3 bedrooms."
        presence = parse_markdown_for_field_presence(markdown)
        assert presence["price"] is False

    def test_address_detection_postcode(self):
        """Detect UK postcodes like SW1A 1AA."""
        markdown = "Located at 123 High Street, London SW1A 1AA"
        presence = parse_markdown_for_field_presence(markdown)
        assert presence["address_road"] is True
        assert presence["postcode"] is True

    def test_address_detection_street_words(self):
        """Detect addresses via street words (road, lane, etc.)."""
        markdown = "Property is on Baker Street in central London."
        presence = parse_markdown_for_field_presence(markdown)
        assert presence["address_road"] is True

    def test_image_detection_markdown(self):
        """Detect markdown image syntax."""
        markdown = "![Living Room](http://example.com/img1.jpg)\n![Bedroom](http://example.com/img2.jpg)"
        presence = parse_markdown_for_field_presence(markdown)
        assert presence["image_urls"] is True

    def test_image_detection_urls(self):
        """Detect plain image URLs."""
        markdown = "Photo: https://example.com/property/photo1.jpg"
        presence = parse_markdown_for_field_presence(markdown)
        assert presence["image_urls"] is True

    def test_no_images(self):
        """No image patterns should return False."""
        markdown = "Just some plain text description."
        presence = parse_markdown_for_field_presence(markdown)
        assert presence["image_urls"] is False

    def test_bedrooms_detection(self):
        """Detect bedroom counts."""
        markdown = "This 3 bedroom house has great views."
        presence = parse_markdown_for_field_presence(markdown)
        assert presence["bedrooms"] is True

    def test_bathrooms_detection(self):
        """Detect bathroom counts."""
        markdown = "Features 2 bathrooms and a modern kitchen."
        presence = parse_markdown_for_field_presence(markdown)
        assert presence["bathrooms"] is True

    def test_agent_detection(self):
        """Detect estate agent mentions."""
        markdown = "Marketed by Foxtons Estate Agent"
        presence = parse_markdown_for_field_presence(markdown)
        assert presence["estate_agent_name"] is True

    def test_property_type_detection(self):
        """Detect property type mentions."""
        markdown = "A beautiful semi-detached property in quiet area."
        presence = parse_markdown_for_field_presence(markdown)
        assert presence["property_type"] is True

    def test_floorplan_detection(self):
        """Detect floorplan mentions."""
        markdown = "View the floor plan for this property below."
        presence = parse_markdown_for_field_presence(markdown)
        assert presence["floorplan_urls"] is True

    def test_transaction_type_detection(self):
        """Detect sale/rent transaction type."""
        markdown = "This property is for sale at £350,000."
        presence = parse_markdown_for_field_presence(markdown)
        assert presence["transaction_type"] is True

    def test_description_detection(self):
        """Detect description presence via paragraph length."""
        short = "Too short."
        presence_short = parse_markdown_for_field_presence(short)
        assert presence_short["description"] is False

        long_text = "A " * 60 + "word paragraph."
        presence_long = parse_markdown_for_field_presence(long_text)
        assert presence_long["description"] is True

    def test_empty_markdown(self):
        """Empty markdown should return empty dict."""
        presence = parse_markdown_for_field_presence("")
        assert presence == {}

    def test_full_rightmove_style_markdown(self):
        """Test with a realistic property listing markdown."""
        markdown = """
# 3 Bedroom Semi-Detached House

£275,000 Guide Price

Located at 45 Victoria Road, Manchester M20 3GH

## Description

A well-presented three bedroom semi-detached family home situated in a
popular residential location. The property briefly comprises entrance
hallway, lounge, dining room, kitchen. On the first floor there are
three bedrooms and a family bathroom. Externally there is a driveway
providing off road parking and an enclosed rear garden.

## Key Features

- 3 bedrooms
- 2 bathrooms
- Semi-detached
- Garden
- Parking

## Floor Plan

![Floor Plan](http://example.com/floorplan.jpg)

## Photos

![Front](http://example.com/front.jpg)
![Garden](http://example.com/garden.jpg)
![Kitchen](http://example.com/kitchen.png)

Marketed by Purplebricks Estate Agent
45 Agent Road, Manchester M1 1AA
        """
        presence = parse_markdown_for_field_presence(markdown)

        assert presence["price"] is True
        assert presence["address_road"] is True
        assert presence["postcode"] is True
        assert presence["image_urls"] is True
        assert presence["bedrooms"] is True
        assert presence["bathrooms"] is True
        assert presence["property_type"] is True
        assert presence["estate_agent_name"] is True
        assert presence["floorplan_urls"] is True
        assert presence["description"] is True
