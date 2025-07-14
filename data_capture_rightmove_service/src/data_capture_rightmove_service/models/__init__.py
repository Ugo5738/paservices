"""
Database models for the Data Capture Rightmove Service.
"""

from data_capture_rightmove_service.models.base import Base, SuperIdMixin
from data_capture_rightmove_service.models.properties_details_v2 import *
from data_capture_rightmove_service.models.property_details import *
from data_capture_rightmove_service.models.property_for_sale import (
    PropertyDisplayPrice,
    PropertyImage,
    PropertyListing,
)
from data_capture_rightmove_service.models.scrape_event import (
    ScrapeEvent,
    ScrapeEventTypeEnum,
)

# Export all models to make them discoverable by Alembic's 'import *'
__all__ = [
    "Base",
    "SuperIdMixin",
    # Models from properties_details_v2
    "ApiPropertiesDetailsV2",
    "ApiPropertiesDetailsV2Misinfo",
    "ApiPropertiesDetailsV2Status",
    "ApiPropertiesDetailsV2StampDuty",
    "ApiPropertiesDetailsV2Features",
    "ApiPropertiesDetailsV2Branch",
    "ApiPropertiesDetailsV2Brochure",
    "ApiPropertiesDetailsV2Price",
    "ApiPropertiesDetailsV2LocalTax",
    "ApiPropertiesDetailsV2Location",
    "ApiPropertiesDetailsV2SalesInfo",
    "ApiPropertiesDetailsV2Size",
    "ApiPropertiesDetailsV2Mortgage",
    "ApiPropertiesDetailsV2AnalyticsInfo",
    "ApiPropertiesDetailsV2Station",
    "ApiPropertiesDetailsV2Photo",
    "ApiPropertiesDetailsV2Epc",
    "ApiPropertiesDetailsV2Floorplan",
    "ApiPropertiesDetailsV2FeatureRisks",
    "ApiPropertiesDetailsV2FeatureObligations",
    "ApiPropertiesDetailsV2BrochureItem",
    "ApiPropertiesDetailsV2LocationStreetview",
    # Models from property_details
    "ApiPropertyDetails",
    "ApiPropertyDetailAddress",
    "ApiPropertyDetailBroadband",
    "ApiPropertyDetailContactInfo",
    "ApiPropertyDetailContactInfoTelephoneNumber",
    "ApiPropertyDetailCustomer",
    "ApiPropertyDetailCustomerDescription",
    "ApiPropertyDetailCustomerDevelopmentInfo",
    "ApiPropertyDetailCustomerProduct",
    "ApiPropertyDetailDfpAdInfo",
    "ApiPropertyDetailFloorplan",
    "ApiPropertyDetailFloorplanResizedUrl",
    "ApiPropertyDetailImage",
    "ApiPropertyDetailImageResizedUrl",
    "ApiPropertyDetailIndustryAffiliation",
    "ApiPropertyDetailInfoReelItem",
    "ApiPropertyDetailListingHistory",
    "ApiPropertyDetailLivingCost",
    "ApiPropertyDetailLocation",
    "ApiPropertyDetailMisInfo",
    "ApiPropertyDetailMortgageCalculator",
    "ApiPropertyDetailNearestStation",
    "ApiPropertyDetailNearestStationType",
    "ApiPropertyDetailPrice",
    "ApiPropertyDetailPropertyUrl",
    "ApiPropertyDetailSharedOwnership",
    "ApiPropertyDetailStaticMapImgUrl",
    "ApiPropertyDetailStatus",
    "ApiPropertyDetailStreetView",
    "ApiPropertyDetailTenure",
    "ApiPropertyDetailText",
    # Models from scrape_event
    "ScrapeEvent",
    "ScrapeEventTypeEnum",
    # Models from property_for_sale
    "PropertyListing",
    "PropertyDisplayPrice",
    "PropertyImage",
]
