"""
Models for the Rightmove property-for-sale/detail API endpoint data.

--- MODIFICATION LOG ---
This file has been updated to support an insert-only, historical snapshot architecture.
Key Changes:
1.  The primary key on the main `ApiPropertyDetails` table is now `snapshot_id` (auto-incrementing).
2.  The Rightmove property ID is stored in the `id` column, which is now non-unique and indexed.
3.  All child tables now use `api_property_snapshot_id` to link to a specific historical record.
4.  All child tables also include a denormalized `api_property_id` for easy querying across all historical
    data for a single property, as per the original requirement.
"""

from sqlalchemy import (
    ARRAY,
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


class ApiPropertyDetails(Base, SuperIdMixin):
    __tablename__ = "api_property_details"

    # --- MODIFICATION: Primary key is now a unique, auto-incrementing "snapshot" ID ---
    snapshot_id = Column(BigInteger, primary_key=True, autoincrement=True)
    # --- MODIFICATION: The Rightmove property ID is now a regular, indexed, non-unique column ---
    id = Column(BigInteger, index=True, nullable=False)

    affordable_buying_scheme = Column(Boolean)
    ai_location_info = Column(Text)
    bathrooms = Column(Integer)
    bedrooms = Column(Integer)
    business_for_sale = Column(Boolean)
    channel = Column(String(50))
    commercial = Column(Boolean)
    country_guide = Column(Text)
    enc_id = Column(Text)
    fees_apply = Column(JSONB)
    lettings = Column(JSONB)
    property_sub_type = Column(Text)
    show_school_info = Column(Boolean)
    sold_property_type = Column(String(100))
    terms_of_use = Column(Text)
    transaction_type = Column(String(50))
    brochures = Column(JSONB)
    commercial_use_classes = Column(ARRAY(Text))
    epc_graphs = Column(JSONB)
    key_features = Column(ARRAY(Text))
    nearest_airports = Column(ARRAY(Text))
    rooms = Column(ARRAY(Text))
    sizings = Column(JSONB)
    tags = Column(ARRAY(Text))

    # Relationships
    address = relationship(
        "ApiPropertyDetailAddress",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    broadband = relationship(
        "ApiPropertyDetailBroadband",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    contact_info = relationship(
        "ApiPropertyDetailContactInfo",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    customer = relationship(
        "ApiPropertyDetailCustomer",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    dfp_ad_info = relationship(
        "ApiPropertyDetailDfpAdInfo",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    floorplans = relationship(
        "ApiPropertyDetailFloorplan",
        back_populates="property",
        cascade="all, delete-orphan",
    )
    images = relationship(
        "ApiPropertyDetailImage",
        back_populates="property",
        cascade="all, delete-orphan",
    )
    industry_affiliations = relationship(
        "ApiPropertyDetailIndustryAffiliation",
        back_populates="property",
        cascade="all, delete-orphan",
    )
    info_reel_items = relationship(
        "ApiPropertyDetailInfoReelItem",
        back_populates="property",
        cascade="all, delete-orphan",
    )
    listing_history = relationship(
        "ApiPropertyDetailListingHistory",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    living_costs = relationship(
        "ApiPropertyDetailLivingCost",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    location = relationship(
        "ApiPropertyDetailLocation",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    mis_info = relationship(
        "ApiPropertyDetailMisInfo",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    mortgage_calculator = relationship(
        "ApiPropertyDetailMortgageCalculator",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    nearest_stations = relationship(
        "ApiPropertyDetailNearestStation",
        back_populates="property",
        cascade="all, delete-orphan",
    )
    price = relationship(
        "ApiPropertyDetailPrice",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    property_urls = relationship(
        "ApiPropertyDetailPropertyUrl",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    shared_ownership = relationship(
        "ApiPropertyDetailSharedOwnership",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    static_map_img_urls = relationship(
        "ApiPropertyDetailStaticMapImgUrl",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    status = relationship(
        "ApiPropertyDetailStatus",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    street_view = relationship(
        "ApiPropertyDetailStreetView",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    tenure = relationship(
        "ApiPropertyDetailTenure",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )
    text = relationship(
        "ApiPropertyDetailText",
        back_populates="property",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ApiPropertyDetailAddress(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_addresses"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    country_code = Column(String(10))
    delivery_point_id = Column(BigInteger)
    display_address = Column(Text)
    incode = Column(String(10))
    outcode = Column(String(10))
    uk_country = Column(String(100))
    property = relationship("ApiPropertyDetails", back_populates="address")


class ApiPropertyDetailBroadband(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_broadbands"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    broadband_checker_url = Column(Text)
    disclaimer = Column(Text)
    property = relationship("ApiPropertyDetails", back_populates="broadband")


class ApiPropertyDetailContactInfo(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_contact_infos"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    contact_method = Column(String(100))
    property = relationship("ApiPropertyDetails", back_populates="contact_info")
    telephone_numbers = relationship(
        "ApiPropertyDetailContactInfoTelephoneNumber",
        back_populates="contact_info",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ApiPropertyDetailCustomerProduct(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_customer_products"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    customer_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_detail_customers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_snapshot_id = Column(BigInteger, nullable=False, index=True)
    api_property_id = Column(BigInteger, nullable=False, index=True)

    has_microsite = Column(Boolean)
    customer = relationship("ApiPropertyDetailCustomer", back_populates="products")


class ApiPropertyDetailContactInfoTelephoneNumber(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_contact_info_telephone_numbers"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    contact_info_id = Column(
        BigInteger,
        ForeignKey(
            "rightmove.api_property_detail_contact_infos.id", ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
    )
    api_property_snapshot_id = Column(BigInteger, nullable=False, index=True)
    api_property_id = Column(BigInteger, nullable=False, index=True)

    disclaimer_description = Column(Text)
    disclaimer_text = Column(Text)
    disclaimer_title = Column(Text)
    international_number = Column(String(50))
    local_number = Column(String(50))
    contact_info = relationship(
        "ApiPropertyDetailContactInfo", back_populates="telephone_numbers"
    )


class ApiPropertyDetailCustomer(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_customers"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    banner_ad = Column(Text)
    branch_display_name = Column(String(255))
    branch_id = Column(Integer)
    branch_name = Column(String(255))
    build_to_rent = Column(Boolean)
    build_to_rent_benefits = Column(ARRAY(Text))
    commercial = Column(Boolean)
    company_name = Column(String(255))
    company_trading_name = Column(String(255))
    customer_banner_ad_profile_url = Column(Text)
    customer_mpu_ad_profile_url = Column(Text)
    customer_profile_url = Column(Text)
    customer_properties_url = Column(Text)
    display_address = Column(Text)
    is_new_home_developer = Column(Boolean)
    logo_path = Column(Text)
    mpu_ad = Column(Text)
    show_brochure_lead_modal = Column(Boolean)
    spotlight = Column(Text)
    valuation_form_url = Column(Text)
    video_enabled = Column(Boolean)
    video_url = Column(Text)
    property = relationship("ApiPropertyDetails", back_populates="customer")
    description = relationship(
        "ApiPropertyDetailCustomerDescription",
        back_populates="customer",
        uselist=False,
        cascade="all, delete-orphan",
    )
    development_info = relationship(
        "ApiPropertyDetailCustomerDevelopmentInfo",
        back_populates="customer",
        uselist=False,
        cascade="all, delete-orphan",
    )
    products = relationship(
        "ApiPropertyDetailCustomerProduct",
        back_populates="customer",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ApiPropertyDetailCustomerDescription(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_customer_descriptions"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    customer_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_detail_customers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_snapshot_id = Column(BigInteger, nullable=False, index=True)
    api_property_id = Column(BigInteger, nullable=False, index=True)

    is_truncated = Column(Boolean)
    truncated_description_html = Column(Text)
    customer = relationship("ApiPropertyDetailCustomer", back_populates="description")


class ApiPropertyDetailCustomerDevelopmentInfo(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_customer_development_infos"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    customer_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_detail_customers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_snapshot_id = Column(BigInteger, nullable=False, index=True)
    api_property_id = Column(BigInteger, nullable=False, index=True)

    site_plan_uri = Column(Text)
    microsite_features = Column(ARRAY(Text))
    customer = relationship(
        "ApiPropertyDetailCustomer", back_populates="development_info"
    )


class ApiPropertyDetailDfpAdInfo(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_dfp_ad_infos"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    channel = Column(String(50))
    targeting = Column(JSONB)  # API returns array of objects, JSONB is flexible
    property = relationship("ApiPropertyDetails", back_populates="dfp_ad_info")


class ApiPropertyDetailFloorplan(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_floorplans"
    id = Column(Integer, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    caption = Column(String(255))
    type = Column(String(50))
    url = Column(Text)
    property = relationship("ApiPropertyDetails", back_populates="floorplans")
    resized_floorplan_urls = relationship(
        "ApiPropertyDetailFloorplanResizedUrl",
        back_populates="floorplan",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ApiPropertyDetailFloorplanResizedUrl(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_floorplan_resized_floorplan_urls"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    floorplan_id = Column(
        Integer,
        ForeignKey("rightmove.api_property_detail_floorplans.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_snapshot_id = Column(BigInteger, nullable=False, index=True)
    api_property_id = Column(BigInteger, nullable=False, index=True)

    size_296x197 = Column(Text)
    floorplan = relationship(
        "ApiPropertyDetailFloorplan", back_populates="resized_floorplan_urls"
    )


class ApiPropertyDetailImage(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_images"
    id = Column(Integer, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    caption = Column(String(255))
    url = Column(Text)
    property = relationship("ApiPropertyDetails", back_populates="images")
    resized_image_urls = relationship(
        "ApiPropertyDetailImageResizedUrl",
        back_populates="image",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ApiPropertyDetailImageResizedUrl(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_image_resized_image_urls"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    image_id = Column(
        Integer,
        ForeignKey("rightmove.api_property_detail_images.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_snapshot_id = Column(BigInteger, nullable=False, index=True)
    api_property_id = Column(BigInteger, nullable=False, index=True)

    size_135x100 = Column(Text)
    size_476x317 = Column(Text)
    size_656x437 = Column(Text)
    image = relationship("ApiPropertyDetailImage", back_populates="resized_image_urls")


class ApiPropertyDetailIndustryAffiliation(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_industry_affiliations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    image_path = Column(Text)
    name = Column(Text)
    property = relationship(
        "ApiPropertyDetails", back_populates="industry_affiliations"
    )


class ApiPropertyDetailInfoReelItem(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_info_reel_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    primary_text = Column(Text)
    secondary_text = Column(Text)
    title = Column(Text)
    tooltip_text = Column(Text)
    type = Column(Text)
    property = relationship("ApiPropertyDetails", back_populates="info_reel_items")


class ApiPropertyDetailListingHistory(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_listing_history"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    listing_update_reason = Column(Text)
    property = relationship("ApiPropertyDetails", back_populates="listing_history")


class ApiPropertyDetailLivingCost(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_living_costs"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    annual_ground_rent = Column(Text)
    annual_service_charge = Column(Text)
    council_tax_band = Column(String(10))
    council_tax_exempt = Column(Boolean)
    council_tax_included = Column(Boolean)
    domestic_rates = Column(Text)
    ground_rent_percentage_increase = Column(Text)
    ground_rent_review_period_in_years = Column(Text)
    property = relationship("ApiPropertyDetails", back_populates="living_costs")


class ApiPropertyDetailLocation(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_locations"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    circle_radius_on_map = Column(Integer)
    latitude = Column(Numeric(10, 8))
    longitude = Column(Numeric(11, 8))
    pin_type = Column(String(50))
    show_map = Column(Boolean)
    zoom_level = Column(Integer)
    property = relationship("ApiPropertyDetails", back_populates="location")


class ApiPropertyDetailMisInfo(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_mis_infos"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    branch_id = Column(Integer)
    brand_plus = Column(Boolean)
    featured_property = Column(Boolean)
    offer_advert_stamp_type_id = Column(Text)
    premium_display = Column(Boolean)
    premium_display_stamp_id = Column(Text)
    property = relationship("ApiPropertyDetails", back_populates="mis_info")


class ApiPropertyDetailMortgageCalculator(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_mortgage_calculators"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    price = Column(BigInteger)
    property_type_alias = Column(String(100))
    property = relationship("ApiPropertyDetails", back_populates="mortgage_calculator")


class ApiPropertyDetailNearestStation(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_nearest_stations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    distance = Column(Numeric(18, 16))
    name = Column(Text)
    unit = Column(Text)
    property = relationship("ApiPropertyDetails", back_populates="nearest_stations")
    types = relationship(
        "ApiPropertyDetailNearestStationType",
        back_populates="station",
        cascade="all, delete-orphan",
    )


class ApiPropertyDetailNearestStationType(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_nearest_station_types"
    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(
        Integer,
        ForeignKey(
            "rightmove.api_property_detail_nearest_stations.id", ondelete="CASCADE"
        ),
        nullable=False,
    )
    api_property_snapshot_id = Column(BigInteger, nullable=False, index=True)
    api_property_id = Column(BigInteger, nullable=False, index=True)

    type = Column(String(100))
    station = relationship("ApiPropertyDetailNearestStation", back_populates="types")


class ApiPropertyDetailPrice(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_prices"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    display_price_qualifier = Column(String(255))
    exchange_rate = Column(Text)
    message = Column(Text)
    price_per_sq_ft = Column(String(100))
    primary_price = Column(String(100))
    secondary_price = Column(Text)
    property = relationship("ApiPropertyDetails", back_populates="price")


class ApiPropertyDetailPropertyUrl(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_property_urls"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    nearby_sold_properties_url = Column(Text)
    similar_properties_url = Column(Text)
    property = relationship("ApiPropertyDetails", back_populates="property_urls")


class ApiPropertyDetailSharedOwnership(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_shared_ownerships"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    ownership_percentage = Column(Numeric(10, 4))
    rent_frequency = Column(String(100))
    rent_price = Column(Numeric(12, 2))
    shared_ownership = Column(Boolean)  # API field is 'sharedOwnership'
    property = relationship("ApiPropertyDetails", back_populates="shared_ownership")


class ApiPropertyDetailStaticMapImgUrl(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_static_map_img_urls"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    static_map_img_url_desktop_large = Column(Text)
    static_map_img_url_desktop_small = Column(Text)
    static_map_img_url_mobile = Column(Text)
    static_map_img_url_tablet = Column(Text)
    property = relationship("ApiPropertyDetails", back_populates="static_map_img_urls")


class ApiPropertyDetailStatus(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_status"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    archived = Column(Boolean)
    published = Column(Boolean)
    property = relationship("ApiPropertyDetails", back_populates="status")


class ApiPropertyDetailStreetView(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_street_views"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    heading = Column(Text)
    latitude = Column(Numeric(10, 8))
    longitude = Column(Numeric(11, 8))
    pitch = Column(Text)
    zoom = Column(Text)
    property = relationship("ApiPropertyDetails", back_populates="street_view")


class ApiPropertyDetailTenure(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_tenures"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    message = Column(Text)
    tenure_type = Column(String(100))
    years_remaining_on_lease = Column(Integer)
    property = relationship("ApiPropertyDetails", back_populates="tenure")


class ApiPropertyDetailText(Base, SuperIdMixin):
    __tablename__ = "api_property_detail_texts"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_property_snapshot_id = Column(
        BigInteger,
        ForeignKey("rightmove.api_property_details.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    api_property_id = Column(BigInteger, nullable=False, index=True)

    auction_fees_disclaimer = Column(Text)
    description = Column(Text)
    disclaimer = Column(Text)
    guide_price_disclaimer = Column(Text)
    new_homes_brochure_disclaimer = Column(Text)
    page_title = Column(Text)
    property_phrase = Column(String(255))
    reserve_price_disclaimer = Column(Text)
    share_description = Column(Text)
    share_text = Column(Text)
    short_description = Column(Text)
    static_map_disclaimer_text = Column(Text)
    property = relationship("ApiPropertyDetails", back_populates="text")
