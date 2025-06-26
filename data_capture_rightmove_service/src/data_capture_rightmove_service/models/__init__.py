"""
Database models for the Data Capture Rightmove Service.
"""

from data_capture_rightmove_service.models.base import Base, SuperIdMixin
from data_capture_rightmove_service.models.properties_details_v2 import (
    ApiPropertiesDetailsV2,
    ApiPropertiesDetailsV2Branch,
    ApiPropertiesDetailsV2Floorplan,
    ApiPropertiesDetailsV2Location,
    ApiPropertiesDetailsV2Photo,
    ApiPropertiesDetailsV2Price,
    ApiPropertiesDetailsV2Station,
)
from data_capture_rightmove_service.models.property_details import (
    ApiPropertyDetailCustomer,
    ApiPropertyDetailFloorplan,
    ApiPropertyDetailImage,
    ApiPropertyDetailPrice,
    ApiPropertyDetails,
)

# Export all models
__all__ = [
    "Base",
    "SuperIdMixin",
    "ApiPropertiesDetailsV2",
    "ApiPropertiesDetailsV2Branch",
    "ApiPropertiesDetailsV2Price",
    "ApiPropertiesDetailsV2Location",
    "ApiPropertiesDetailsV2Photo",
    "ApiPropertiesDetailsV2Floorplan",
    "ApiPropertiesDetailsV2Station",
    "ApiPropertyDetails",
    "ApiPropertyDetailPrice",
    "ApiPropertyDetailCustomer",
    "ApiPropertyDetailImage",
    "ApiPropertyDetailFloorplan",
]
