"""
CRUD operations for database interactions in the Data Capture Rightmove Service.
"""

from data_capture_rightmove_service.crud.properties_details import (
    store_properties_details,
    get_property_details_by_id,
    get_all_property_ids
)
from data_capture_rightmove_service.crud.property_details import (
    store_property_details,
    get_property_sale_details_by_id,
    get_all_property_sale_ids
)

__all__ = [
    'store_properties_details',
    'get_property_details_by_id',
    'get_all_property_ids',
    'store_property_details',
    'get_property_sale_details_by_id',
    'get_all_property_sale_ids'
]
