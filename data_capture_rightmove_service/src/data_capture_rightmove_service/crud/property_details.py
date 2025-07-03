"""
CRUD operations for the property-for-sale/detail endpoint data.
"""

import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from data_capture_rightmove_service.models.property_details import *
from data_capture_rightmove_service.utils.db_utils import normalize_model_instance
from data_capture_rightmove_service.utils.logging_config import logger
from data_capture_rightmove_service.utils.property_mapper import map_property_data


def camel_to_snake(name: str) -> str:
    """Converts a camelCase string to a snake_case string."""
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


import json

from sqlalchemy import String, Text


def map_data_to_model(data: Dict[str, Any], model_class) -> Dict[str, Any]:
    """
    Takes a dictionary with camelCase keys and maps it to a dictionary with
    snake_case keys suitable for a SQLAlchemy model.

    Automatically converts dictionary values to JSON strings for TEXT/String columns.
    """
    snake_case_data = {}
    valid_model_keys = {c.name: c for c in model_class.__table__.columns}

    for key, value in data.items():
        snake_key = camel_to_snake(key)

        # Special case for 'id' which is the primary key in the main model
        if model_class == ApiPropertyDetails and key == "id":
            snake_key = "id"

        if snake_key in valid_model_keys:
            # If we're storing a dictionary in a Text/String column, serialize it to JSON
            column = valid_model_keys[snake_key]
            if isinstance(value, dict) and isinstance(column.type, (Text, String)):
                logger.debug(
                    f"Converting dict to JSON string for {snake_key} in {model_class.__name__}"
                )
                snake_case_data[snake_key] = json.dumps(value)
            else:
                snake_case_data[snake_key] = value
        else:
            logger.debug(
                f"Skipping unmapped key '{key}' (as '{snake_key}') for model {model_class.__name__}"
            )

    return snake_case_data


async def store_property_details(
    db: AsyncSession, data: Dict[str, Any], super_id: uuid.UUID
) -> Tuple[bool, str]:
    """
    Store property details data from the property-for-sale/detail API.
    """
    property_data = data.get("data")
    if not property_data:
        return False, "API response is missing the 'data' object."

    property_id = property_data.get("id")
    if not property_id:
        return False, "Could not find 'id' in property data."

    try:
        # 1. Main object
        main_values = map_property_data(property_data, ApiPropertyDetails)
        main_values["id"] = property_id
        main_values["super_id"] = super_id
        property_record = ApiPropertyDetails(**main_values)
        db.add(property_record)
        await db.flush()
        snapshot_id = property_record.snapshot_id

        instance_cache = {}

        # 2. One-to-one relationships
        one_to_one_models = {
            "address": ApiPropertyDetailAddress,
            "broadband": ApiPropertyDetailBroadband,
            "listingHistory": ApiPropertyDetailListingHistory,
            "livingCosts": ApiPropertyDetailLivingCost,
            "location": ApiPropertyDetailLocation,
            "misInfo": ApiPropertyDetailMisInfo,
            "mortgageCalculator": ApiPropertyDetailMortgageCalculator,
            "prices": ApiPropertyDetailPrice,
            "propertyUrls": ApiPropertyDetailPropertyUrl,
            "sharedOwnership": ApiPropertyDetailSharedOwnership,
            "staticMapImgUrls": ApiPropertyDetailStaticMapImgUrl,
            "status": ApiPropertyDetailStatus,
            "streetView": ApiPropertyDetailStreetView,
            "tenure": ApiPropertyDetailTenure,
            "text": ApiPropertyDetailText,
            "contactInfo": ApiPropertyDetailContactInfo,
            "customer": ApiPropertyDetailCustomer,
            "dfpAdInfo": ApiPropertyDetailDfpAdInfo,
        }
        for api_key, model_class in one_to_one_models.items():
            if api_key in property_data and property_data[api_key]:
                nested_data = property_data[api_key]
                nested_values = map_property_data(nested_data, model_class)
                # --- FIX: Use correct snapshot and property IDs ---
                nested_values["api_property_snapshot_id"] = snapshot_id
                nested_values["api_property_id"] = property_id
                nested_values["super_id"] = super_id

                instance = model_class(**nested_values)
                db.add(instance)
                instance_cache[api_key] = instance

        await db.flush()

        # 3. Deeply nested relationships
        if "customer" in instance_cache:
            customer_instance = instance_cache["customer"]
            customer_data = property_data.get("customer", {})
            if (
                "customerDescription" in customer_data
                and customer_data["customerDescription"]
            ):
                desc_values = map_property_data(
                    customer_data["customerDescription"],
                    ApiPropertyDetailCustomerDescription,
                )
                desc_values["customer_id"] = customer_instance.id
                desc_values["api_property_snapshot_id"] = snapshot_id
                desc_values["api_property_id"] = property_id
                desc_values["super_id"] = super_id
                db.add(ApiPropertyDetailCustomerDescription(**desc_values))
            if "developmentInfo" in customer_data and customer_data["developmentInfo"]:
                dev_values = map_property_data(
                    customer_data["developmentInfo"],
                    ApiPropertyDetailCustomerDevelopmentInfo,
                )
                dev_values["customer_id"] = customer_instance.id
                dev_values["api_property_snapshot_id"] = snapshot_id
                dev_values["api_property_id"] = property_id
                dev_values["super_id"] = super_id
                db.add(ApiPropertyDetailCustomerDevelopmentInfo(**dev_values))
            if "products" in customer_data and customer_data["products"]:
                prod_values = map_property_data(
                    customer_data["products"], ApiPropertyDetailCustomerProduct
                )
                prod_values["customer_id"] = customer_instance.id
                prod_values["api_property_snapshot_id"] = snapshot_id
                prod_values["api_property_id"] = property_id
                prod_values["super_id"] = super_id
                db.add(ApiPropertyDetailCustomerProduct(**prod_values))

        if "contactInfo" in instance_cache:
            contact_instance = instance_cache["contactInfo"]
            contact_data = property_data.get("contactInfo", {})
            if "telephoneNumbers" in contact_data and contact_data["telephoneNumbers"]:
                phone_values = map_property_data(
                    contact_data["telephoneNumbers"],
                    ApiPropertyDetailContactInfoTelephoneNumber,
                )
                # --- FIX: Use correct keyword 'contact_info_id' ---
                phone_values["contact_info_id"] = contact_instance.id
                phone_values["api_property_snapshot_id"] = snapshot_id
                phone_values["api_property_id"] = property_id
                phone_values["super_id"] = super_id
                db.add(ApiPropertyDetailContactInfoTelephoneNumber(**phone_values))

        # 4. One-to-many relationships
        one_to_many_models = {
            "floorplans": ApiPropertyDetailFloorplan,
            "images": ApiPropertyDetailImage,
            "industryAffiliations": ApiPropertyDetailIndustryAffiliation,
            "infoReelItems": ApiPropertyDetailInfoReelItem,
            "nearestStations": ApiPropertyDetailNearestStation,
        }

        for api_key, model_class in one_to_many_models.items():
            if api_key in property_data and isinstance(property_data[api_key], list):
                for item_data in property_data[api_key]:
                    item_values = map_property_data(item_data, model_class)
                    item_values["api_property_snapshot_id"] = snapshot_id
                    item_values["api_property_id"] = property_id
                    item_values["super_id"] = super_id

                    item_instance = model_class(**item_values)
                    db.add(item_instance)

                    # Handle resizing URLs and station types after flushing to get the ID
                    await db.flush()
                    if (
                        api_key == "floorplans"
                        and "resizedFloorplanUrls" in item_data
                        and item_data["resizedFloorplanUrls"]
                    ):
                        resized_values = map_property_data(
                            item_data["resizedFloorplanUrls"],
                            ApiPropertyDetailFloorplanResizedUrl,
                        )
                        resized_values["floorplan_id"] = item_instance.id
                        resized_values["api_property_snapshot_id"] = snapshot_id
                        resized_values["api_property_id"] = property_id
                        resized_values["super_id"] = super_id
                        db.add(ApiPropertyDetailFloorplanResizedUrl(**resized_values))
                    if (
                        api_key == "images"
                        and "resizedImageUrls" in item_data
                        and item_data["resizedImageUrls"]
                    ):
                        resized_values = map_property_data(
                            item_data["resizedImageUrls"],
                            ApiPropertyDetailImageResizedUrl,
                        )
                        resized_values["image_id"] = item_instance.id
                        resized_values["api_property_snapshot_id"] = snapshot_id
                        resized_values["api_property_id"] = property_id
                        resized_values["super_id"] = super_id
                        db.add(ApiPropertyDetailImageResizedUrl(**resized_values))
                    if (
                        api_key == "nearestStations"
                        and "types" in item_data
                        and isinstance(item_data["types"], list)
                    ):
                        for type_name in item_data["types"]:
                            type_values = {
                                "station_id": item_instance.id,
                                "type": type_name,
                                "api_property_snapshot_id": snapshot_id,
                                "api_property_id": property_id,
                                "super_id": super_id,
                            }
                            db.add(ApiPropertyDetailNearestStationType(**type_values))

        logger.info(
            f"Successfully prepared property-for-sale snapshot for {property_id}."
        )
        return True, f"Successfully stored property-for-sale {property_id} details."

    except IntegrityError as e:
        await db.rollback()
        logger.error(
            f"DB Integrity Error for property {property_id}: {e.orig}", exc_info=True
        )
        return False, f"Database integrity error: {e.orig}"
    except Exception as e:
        await db.rollback()
        logger.error(
            f"Error storing property-for-sale {property_id}: {e}", exc_info=True
        )
        return False, f"Error storing property-for-sale details: {e}"


async def get_property_sale_details_by_id(
    db: AsyncSession, property_id: int
) -> Optional[Dict[str, Any]]:
    """
    Get property sale details by ID with all related information,
    using efficient relationship loading.

    Args:
        db: Database session
        property_id: Rightmove property ID

    Returns:
        Optional[Dict[str, Any]]: Property details or None if not found
    """
    try:
        # Define the query with eager loading for all relationships
        stmt = (
            select(ApiPropertyDetails)
            .where(ApiPropertyDetails.id == property_id)
            .options(
                # Load one-to-one relationships
                selectinload(ApiPropertyDetails.address),
                selectinload(ApiPropertyDetails.broadband),
                selectinload(ApiPropertyDetails.prices),
                selectinload(ApiPropertyDetails.customer).selectinload(
                    ApiPropertyDetailCustomer.description
                ),
                selectinload(ApiPropertyDetails.listing_history),
                selectinload(ApiPropertyDetails.living_costs),
                selectinload(ApiPropertyDetails.location),
                selectinload(ApiPropertyDetails.tenure),
                selectinload(ApiPropertyDetails.text),
                # Load one-to-many relationships
                selectinload(ApiPropertyDetails.images).selectinload(
                    ApiPropertyDetailImage.resized_image_urls
                ),
                selectinload(ApiPropertyDetails.floorplans).selectinload(
                    ApiPropertyDetailFloorplan.resized_floorplan_urls
                ),
                selectinload(ApiPropertyDetails.nearest_stations).selectinload(
                    ApiPropertyDetailNearestStation.types
                ),
                selectinload(ApiPropertyDetails.info_reel_items),
            )
        )

        result = await db.execute(stmt)
        property_details = result.scalar_one_or_none()

        if not property_details:
            return None

        # --- Helper function to convert model to dict ---
        def to_dict(obj):
            if obj is None:
                return None
            # Exclude SQLAlchemy internal state and relationship attributes that will be handled separately
            return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

        # --- Build the final response dictionary ---
        response_dict = to_dict(property_details)

        # Manually add the loaded relationships to the dictionary
        response_dict["address"] = to_dict(property_details.address)
        response_dict["broadband"] = to_dict(property_details.broadband)
        response_dict["prices"] = to_dict(property_details.prices)

        # Handle nested customer description
        if property_details.customer:
            response_dict["customer"] = to_dict(property_details.customer)
            if property_details.customer.description:
                response_dict["customer"]["description"] = to_dict(
                    property_details.customer.description
                )

        # Handle lists of related objects
        response_dict["images"] = []
        for img in property_details.images:
            img_dict = to_dict(img)
            img_dict["resized_image_urls"] = to_dict(img.resized_image_urls)
            response_dict["images"].append(img_dict)

        response_dict["floorplans"] = []
        for fp in property_details.floorplans:
            fp_dict = to_dict(fp)
            fp_dict["resized_floorplan_urls"] = to_dict(fp.resized_floorplan_urls)
            response_dict["floorplans"].append(fp_dict)

        response_dict["nearest_stations"] = []
        for station in property_details.nearest_stations:
            station_dict = to_dict(station)
            station_dict["types"] = [t.type for t in station.types]
            response_dict["nearest_stations"].append(station_dict)

        response_dict["info_reel_items"] = [
            to_dict(item) for item in property_details.info_reel_items
        ]

        return response_dict

    except Exception as e:
        logger.error(
            f"Error retrieving property sale details for ID {property_id}: {e}",
            exc_info=True,
        )
        return None


async def get_all_property_sale_ids(
    db: AsyncSession, limit: int = 1000, offset: int = 0
) -> List[int]:
    """
    Get all property sale IDs stored in the database.

    Args:
        db: Database session
        limit: Maximum number of IDs to return
        offset: Offset for pagination

    Returns:
        List[int]: List of property IDs
    """
    try:
        stmt = (
            select(ApiPropertyDetails.id)
            .order_by(ApiPropertyDetails.id)
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        return [row[0] for row in result.fetchall()]
    except Exception as e:
        logger.error(f"Error retrieving all property sale IDs: {str(e)}")
        return []
