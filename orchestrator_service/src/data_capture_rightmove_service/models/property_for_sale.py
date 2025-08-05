# data_capture_rightmove_service/src/models/property_for_sale.py

"""
SQLAlchemy models for the data returned by the Rightmove '/buy/property-for-sale'
list endpoint. This uses the hybrid flattened approach.
"""

from sqlalchemy import (
    ARRAY,
    DECIMAL,
    JSON,
    TIMESTAMP,
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .base import Base, SuperIdMixin


class PropertyListing(Base, SuperIdMixin):
    __tablename__ = "property_listings"

    # A unique, auto-incrementing primary key for each snapshot record.
    snapshot_id = Column(BigInteger, primary_key=True, autoincrement=True)

    # The Rightmove property ID. This is not unique, as we can have multiple snapshots for the same property.
    id = Column(BigInteger, nullable=False, index=True)

    api_source_endpoint = Column(String(100), nullable=False)

    # Top-Level Property Attributes (Flattened)
    added_or_reduced = Column(String(255))
    auction = Column(Boolean)
    bathrooms = Column(Integer)
    bedrooms = Column(Integer)
    channel = Column(String(50))
    commercial = Column(Boolean)
    contact_url = Column(Text)
    country_code = Column(String(10))
    development = Column(Boolean)
    display_address = Column(String(512))
    display_size = Column(String(100))
    display_status = Column(String(255))
    distance = Column(DECIMAL(10, 4))
    enhanced_listing = Column(Boolean)
    enquired_timestamp = Column(TIMESTAMP)
    featured_property = Column(Boolean)
    fees_apply = Column(Boolean)
    fees_apply_text = Column(Text)
    first_visible_date = Column(TIMESTAMP)
    formatted_branch_name = Column(String(255))
    formatted_distance = Column(String(100))
    has_brand_plus = Column(Boolean)
    heading = Column(Text)
    hidden = Column(Boolean)
    is_recent = Column(Boolean)
    keyword_match_type = Column(String(100))
    keywords_json = Column(JSON)
    number_of_floorplans = Column(Integer)
    number_of_images = Column(Integer)
    number_of_virtual_tours = Column(Integer)
    online_viewings_available = Column(Boolean)
    premium_listing = Column(Boolean)
    property_sub_type = Column(String(100))
    property_type_full_description = Column(String(255))
    property_url = Column(Text)
    residential = Column(Boolean)
    saved = Column(Boolean)
    show_on_map = Column(Boolean)
    static_map_url = Column(Text)
    students = Column(Boolean)
    summary = Column(Text)
    transaction_type = Column(String(50))

    # Flattened 'customer' object fields
    customer_branch_display_name = Column(String(255))
    customer_branch_id = Column(Integer)
    customer_branch_landing_page_url = Column(Text)
    customer_branch_name = Column(String(255))
    customer_brand_plus_logo_uri = Column(Text)
    customer_brand_plus_logo_url = Column(Text)
    customer_brand_trading_name = Column(String(255))
    customer_build_to_rent = Column(Boolean)
    customer_build_to_rent_benefits_json = Column(JSON)
    customer_commercial = Column(Boolean)
    customer_contact_telephone = Column(String(50))
    customer_development = Column(Boolean)
    customer_development_content = Column(Text)
    customer_enhanced_listing = Column(Boolean)
    customer_show_on_map = Column(Boolean)
    customer_show_reduced_properties = Column(Boolean)

    # Flattened 'listingUpdate' object fields
    listing_update_date = Column(TIMESTAMP)
    listing_update_reason = Column(String(100))

    # Flattened 'location' object fields
    location_latitude = Column(DECIMAL(10, 8))
    location_longitude = Column(DECIMAL(11, 8))

    # Flattened 'lozengeModel' object fields
    lozenge_model_matching_lozenges_json = Column(JSON)

    # Flattened 'price' object fields (1-to-1 data)
    price_amount = Column(DECIMAL(14, 2))
    price_currency_code = Column(String(10))
    price_frequency = Column(String(50))

    # Flattened 'productLabel' object fields
    product_label_text = Column(String(255))
    product_label_spotlight_label = Column(Boolean)

    # Flattened 'propertyImages' object fields (1-to-1 data)
    property_images_main_image_src = Column(Text)
    property_images_main_map_image_src = Column(Text)

    # Relationships to child tables
    display_prices = relationship(
        "PropertyDisplayPrice",
        back_populates="listing",
        cascade="all, delete-orphan",
    )
    images = relationship(
        "PropertyImage", back_populates="listing", cascade="all, delete-orphan"
    )


class PropertyDisplayPrice(Base, SuperIdMixin):
    __tablename__ = "property_display_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    property_listing_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.property_listings.snapshot_id"),
        nullable=False,
    )
    display_price = Column(String(100))
    display_price_qualifier = Column(String(255))

    listing = relationship("PropertyListing", back_populates="display_prices")


class PropertyImage(Base, SuperIdMixin):
    __tablename__ = "property_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    property_listing_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.property_listings.snapshot_id"),
        nullable=False,
    )
    caption = Column(String(255))
    src_url = Column(Text)
    url = Column(Text)

    listing = relationship("PropertyListing", back_populates="images")
