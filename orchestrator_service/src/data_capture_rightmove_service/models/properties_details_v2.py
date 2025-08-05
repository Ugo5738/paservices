"""
Models for the Rightmove properties/details v2 API endpoint data.
This module defines SQLAlchemy models that map to the tables in the rightmove schema.

--- MODIFICATION LOG ---
This file has been updated to support an insert-only, historical snapshot architecture.
Key Changes:
1.  The primary key on the main `ApiPropertiesDetailsV2` table is now `snapshot_id` (auto-incrementing).
2.  The Rightmove property ID is stored in the `id` column, which is now non-unique and indexed.
3.  All child tables now use `api_property_snapshot_id` to link to a specific historical record.
4.  All child tables also include a denormalized `api_property_id` for easy querying across all historical
    data for a single property, as per the original requirement.
"""

from sqlalchemy import (
    ARRAY,
    TIMESTAMP,
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from data_capture_rightmove_service.models.base import Base, SuperIdMixin


class ApiPropertiesDetailsV2(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2"

    # --- MODIFICATION: Primary key is now a unique, auto-incrementing "snapshot" ID ---
    snapshot_id = Column(BigInteger, primary_key=True, autoincrement=True)
    # --- MODIFICATION: The Rightmove property ID is now a regular, indexed, non-unique column ---
    id = Column(BigInteger, index=True, nullable=False)

    transaction_type = Column(String(50))
    channel = Column(String(50))
    bedrooms = Column(Integer)
    bathrooms = Column(Integer)
    address = Column(Text)
    contact_method = Column(String(50))
    property_disclaimer = Column(Text)
    property_phrase = Column(String(255))
    full_description = Column(Text)
    listing_update_reason = Column(String(255))
    property_url = Column(Text)
    school_checker_url = Column(Text)
    lettings_info = Column(JSONB)
    property_display_type = Column(String(100))
    telephone_number = Column(String(50))
    saved = Column(Boolean)
    sold_prices_url = Column(Text)
    market_info_url = Column(Text)
    note = Column(Text)
    link_to_glossary = Column(Text)
    enquired_timestamp = Column(TIMESTAMP(timezone=True), nullable=True)
    key_features = Column(ARRAY(Text))
    tags = Column(ARRAY(Text))
    virtual_tours = Column(JSONB)

    # Relationships
    misinfo = relationship(
        "ApiPropertiesDetailsV2Misinfo",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    status = relationship(
        "ApiPropertiesDetailsV2Status",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    stamp_duty = relationship(
        "ApiPropertiesDetailsV2StampDuty",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    features = relationship(
        "ApiPropertiesDetailsV2Features",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    branch = relationship(
        "ApiPropertiesDetailsV2Branch",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    brochure = relationship(
        "ApiPropertiesDetailsV2Brochure",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    price = relationship(
        "ApiPropertiesDetailsV2Price",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    local_tax = relationship(
        "ApiPropertiesDetailsV2LocalTax",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    location = relationship(
        "ApiPropertiesDetailsV2Location",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    sales_info = relationship(
        "ApiPropertiesDetailsV2SalesInfo",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    size = relationship(
        "ApiPropertiesDetailsV2Size",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    mortgage = relationship(
        "ApiPropertiesDetailsV2Mortgage",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    analytics_info = relationship(
        "ApiPropertiesDetailsV2AnalyticsInfo",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    stations = relationship(
        "ApiPropertiesDetailsV2Station",
        back_populates="property",
        cascade="all, delete-orphan",
    )
    photos = relationship(
        "ApiPropertiesDetailsV2Photo",
        back_populates="property",
        cascade="all, delete-orphan",
    )
    epcs = relationship(
        "ApiPropertiesDetailsV2Epc",
        back_populates="property",
        cascade="all, delete-orphan",
    )
    floorplans = relationship(
        "ApiPropertiesDetailsV2Floorplan",
        back_populates="property",
        cascade="all, delete-orphan",
    )


class ApiPropertiesDetailsV2Misinfo(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_mis_info"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2.snapshot_id", ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    branch_id = Column(Integer)
    offer_advert_stamp_type_id = Column(Text)
    brand_plus = Column(Boolean)
    featured_property = Column(Boolean)
    channel = Column(String(50))
    premium_display = Column(Boolean)
    premium_display_stamp_id = Column(Text)
    country_code = Column(String(10))
    property = relationship("ApiPropertiesDetailsV2", back_populates="misinfo")


class ApiPropertiesDetailsV2Status(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_status"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2.snapshot_id", ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    available = Column(Boolean)
    label = Column(Text)
    property = relationship("ApiPropertiesDetailsV2", back_populates="status")


class ApiPropertiesDetailsV2StampDuty(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_stamp_duty"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2.snapshot_id", ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    country = Column(String(100))
    price = Column(BigInteger)
    buyer_type = Column(Text)
    result = Column(Text)
    property = relationship("ApiPropertiesDetailsV2", back_populates="stamp_duty")


class ApiPropertiesDetailsV2Features(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_features"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2.snapshot_id", ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    electricity = Column(JSONB)
    broadband = Column(JSONB)
    water = Column(JSONB)
    sewerage = Column(JSONB)
    heating = Column(JSONB)
    accessibility = Column(JSONB)
    parking = Column(JSONB)
    garden = Column(JSONB)
    property = relationship("ApiPropertiesDetailsV2", back_populates="features")
    risks = relationship(
        "ApiPropertiesDetailsV2FeatureRisks",
        back_populates="feature",
        uselist=False,
        cascade="all, delete-orphan",
    )
    obligations = relationship(
        "ApiPropertiesDetailsV2FeatureObligations",
        back_populates="feature",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ApiPropertiesDetailsV2Branch(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_branch"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2.snapshot_id", ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    identifier = Column(Integer)
    name = Column(String(255))
    brand_name = Column(String(255))
    display_name = Column(String(255))
    address = Column(Text)
    logo = Column(Text)
    developer = Column(Boolean)
    property = relationship("ApiPropertiesDetailsV2", back_populates="branch")


class ApiPropertiesDetailsV2Brochure(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_brochure"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2.snapshot_id", ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    title = Column(String(255))
    show_brochure_lead = Column(Boolean)
    property = relationship("ApiPropertiesDetailsV2", back_populates="brochure")
    items = relationship(
        "ApiPropertiesDetailsV2BrochureItem",
        back_populates="brochure",
        cascade="all, delete-orphan",
    )


class ApiPropertiesDetailsV2BrochureItem(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_brochure_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    brochure_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2_brochure.id", ondelete="CASCADE"
        ),
        nullable=False,
    )
    api_property_snapshot_id = Column(BigInteger, nullable=False, index=True)
    api_property_id = Column(BigInteger, nullable=False, index=True)

    url = Column(Text)
    caption = Column(String(255))
    brochure = relationship("ApiPropertiesDetailsV2Brochure", back_populates="items")


class ApiPropertiesDetailsV2Price(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_price"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2.snapshot_id", ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    primary_price = Column(String(100))
    secondary_price = Column(String(255))
    property = relationship("ApiPropertiesDetailsV2", back_populates="price")


class ApiPropertiesDetailsV2LocalTax(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_local_tax"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2.snapshot_id", ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    type = Column(String(100))
    status = Column(Text)
    value = Column(String(100))
    property = relationship("ApiPropertiesDetailsV2", back_populates="local_tax")


class ApiPropertiesDetailsV2Location(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_location"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2.snapshot_id", ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    pin_type = Column(String(100))
    latitude = Column(Numeric(10, 8))
    longitude = Column(Numeric(11, 8))
    map_preview_url = Column(Text)
    property = relationship("ApiPropertiesDetailsV2", back_populates="location")
    streetview = relationship(
        "ApiPropertiesDetailsV2LocationStreetview",
        back_populates="location",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ApiPropertiesDetailsV2LocationStreetview(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_location_street_view"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    location_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2_location.id", ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
    )
    api_property_snapshot_id = Column(BigInteger, nullable=False, index=True)
    api_property_id = Column(BigInteger, nullable=False, index=True)

    latitude = Column(Numeric(10, 8))
    longitude = Column(Numeric(11, 8))
    heading = Column(Text)
    pitch = Column(Text)
    zoom = Column(Text)
    url = Column(Text)
    location = relationship(
        "ApiPropertiesDetailsV2Location", back_populates="streetview"
    )


class ApiPropertiesDetailsV2SalesInfo(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_sales_info"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2.snapshot_id", ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    tenure_type = Column(String(100))
    tenure_display_type = Column(String(100))
    ground_rent = Column(Text)
    annual_service_charge = Column(Text)
    estate_charge = Column(Text)
    length_of_lease = Column(Text)
    shared_ownership_percentage = Column(Text)
    shared_ownership_rent = Column(Text)
    property = relationship("ApiPropertiesDetailsV2", back_populates="sales_info")


class ApiPropertiesDetailsV2Size(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_size"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2.snapshot_id", ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    primary_size = Column(String(100))
    secondary_size = Column(Text)
    property = relationship("ApiPropertiesDetailsV2", back_populates="size")


class ApiPropertiesDetailsV2Mortgage(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_mortgage"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2.snapshot_id", ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    price = Column(BigInteger)
    property_type_alias = Column(String(100))
    property = relationship("ApiPropertiesDetailsV2", back_populates="mortgage")


class ApiPropertiesDetailsV2AnalyticsInfo(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_analytics_info"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2.snapshot_id", ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    branch_id = Column(String(50))
    property_id = Column(
        String(50)
    )  # Note: This is a string field from the API, distinct from our integer ID
    online_viewing = Column(String(10))
    image_count = Column(String(10))
    floorplan_count = Column(String(10))
    beds = Column(String(10))
    postcode = Column(String(20))
    property_type = Column(String(100))
    property_sub_type = Column(String(100))
    added = Column(String(20))
    price = Column(String(50))
    tenure = Column(String(100))
    bathrooms = Column(String(10))
    shared_ownership = Column(String(10))
    electricity = Column(String(50))
    broadband = Column(String(50))
    water = Column(String(50))
    sewerage = Column(String(50))
    heating = Column(String(50))
    accessibility = Column(String(50))
    parking = Column(String(50))
    garden = Column(String(50))
    flood_history = Column(String(50))
    flood_defences = Column(String(50))
    flood_risk = Column(String(50))
    listed = Column(String(50))
    restrictions = Column(String(50))
    private_access = Column(String(50))
    public_access = Column(String(50))
    property = relationship("ApiPropertiesDetailsV2", back_populates="analytics_info")


class ApiPropertiesDetailsV2Station(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_stations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2.snapshot_id", ondelete="CASCADE"
        ),
        nullable=False,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    station = Column(String(255))
    distance = Column(Numeric(8, 2))
    type = Column(String(50))
    property = relationship("ApiPropertiesDetailsV2", back_populates="stations")


class ApiPropertiesDetailsV2Photo(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_photos"
    id = Column(Integer, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2.snapshot_id", ondelete="CASCADE"
        ),
        nullable=False,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    url = Column(Text)
    thumbnail_url = Column(Text)
    max_size_url = Column(Text)
    caption = Column(Text)
    property = relationship("ApiPropertiesDetailsV2", back_populates="photos")


class ApiPropertiesDetailsV2Epc(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_epcs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2.snapshot_id", ondelete="CASCADE"
        ),
        nullable=False,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    url = Column(Text)
    caption = Column(String(255))
    property = relationship("ApiPropertiesDetailsV2", back_populates="epcs")


class ApiPropertiesDetailsV2Floorplan(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_floorplans"
    id = Column(Integer, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2.snapshot_id", ondelete="CASCADE"
        ),
        nullable=False,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    url = Column(Text)
    thumbnail_url = Column(Text)
    caption = Column(String(255))
    property = relationship("ApiPropertiesDetailsV2", back_populates="floorplans")


class ApiPropertiesDetailsV2FeatureRisks(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_feature_risks"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    feature_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2_features.id", ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
    )
    api_property_snapshot_id = Column(BigInteger, nullable=False, index=True)
    api_property_id = Column(BigInteger, nullable=False, index=True)

    flood_history = Column(JSONB)
    flood_defences = Column(JSONB)
    flood_risk = Column(JSONB)
    feature = relationship("ApiPropertiesDetailsV2Features", back_populates="risks")


class ApiPropertiesDetailsV2FeatureObligations(Base, SuperIdMixin):
    __tablename__ = "api_properties_details_v2_feature_obligations"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # --- MODIFICATION ---
    feature_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_properties_details_v2_features.id", ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
    )
    api_property_snapshot_id = Column(BigInteger, nullable=False, index=True)
    api_property_id = Column(BigInteger, nullable=False, index=True)

    listed = Column(JSONB)
    restrictions = Column(JSONB)
    private_access = Column(JSONB)
    public_access = Column(JSONB)
    feature = relationship(
        "ApiPropertiesDetailsV2Features", back_populates="obligations"
    )
