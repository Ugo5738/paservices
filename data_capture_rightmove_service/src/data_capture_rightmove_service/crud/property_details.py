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
from sqlalchemy import Text, String

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
                logger.debug(f"Converting dict to JSON string for {snake_key} in {model_class.__name__}")
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

    existing_record = await db.get(ApiPropertyDetails, property_id)
    if existing_record:
        logger.info(
            f"Property ID {property_id} from property-for-sale API already exists. Skipping."
        )
        return True, f"Property {property_id} already exists."

    try:
        main_values = map_data_to_model(property_data, ApiPropertyDetails)
        main_values["id"] = property_id
        main_values["super_id"] = super_id
        property_record = ApiPropertyDetails(**main_values)
        db.add(property_record)

        # Nested one-to-one relationships
        nested_objects = {
            "address": ApiPropertyDetailAddress,
            "broadband": ApiPropertyDetailBroadband,
            "contactInfo": ApiPropertyDetailContactInfo,
            "customer": ApiPropertyDetailCustomer,
            "dfpAdInfo": ApiPropertyDetailDfpAdInfo,
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
        }

        for api_key, model_class in nested_objects.items():
            if api_key in property_data and property_data[api_key]:
                nested_data = property_data[api_key]
                nested_values = map_data_to_model(nested_data, model_class)
                nested_values["api_property_detail_id"] = property_id
                nested_values["super_id"] = super_id
                db.add(model_class(**nested_values))

                # Handle deeply nested objects
                if api_key == "customer" and "customerDescription" in nested_data:
                    desc_data = nested_data["customerDescription"]
                    desc_values = map_data_to_model(
                        desc_data, ApiPropertyDetailCustomerDescription
                    )
                    desc_values["customer_api_property_detail_id"] = property_id
                    desc_values["api_property_detail_id"] = property_id
                    desc_values["super_id"] = super_id
                    db.add(ApiPropertyDetailCustomerDescription(**desc_values))

                if api_key == "contactInfo" and "telephoneNumbers" in nested_data:
                    phone_data = nested_data["telephoneNumbers"]
                    phone_values = map_data_to_model(
                        phone_data, ApiPropertyDetailContactInfoTelephoneNumber
                    )
                    phone_values["contact_info_detail_id"] = property_id
                    phone_values["api_property_detail_id"] = property_id
                    phone_values["super_id"] = super_id
                    db.add(ApiPropertyDetailContactInfoTelephoneNumber(**phone_values))

        # Nested one-to-many relationships
        nested_lists = {
            "floorplans": (
                ApiPropertyDetailFloorplan,
                ApiPropertyDetailFloorplanResizedUrl,
                "resizedFloorplanUrls",
            ),
            "images": (
                ApiPropertyDetailImage,
                ApiPropertyDetailImageResizedUrl,
                "resizedImageUrls",
            ),
        }

        for api_key, (main_model, resized_model, resized_key) in nested_lists.items():
            if api_key in property_data and isinstance(property_data[api_key], list):
                for item_data in property_data[api_key]:
                    main_values = map_data_to_model(item_data, main_model)
                    main_values["api_property_detail_id"] = property_id
                    main_values["super_id"] = super_id
                    main_instance = main_model(**main_values)
                    db.add(main_instance)
                    await db.flush()  # Flush to get the ID of the main instance

                    if resized_key in item_data and item_data[resized_key]:
                        resized_values = map_data_to_model(
                            item_data[resized_key], resized_model
                        )
                        if api_key == "floorplans":
                            resized_values["floorplan_id"] = main_instance.id
                        elif api_key == "images":
                            resized_values["image_id"] = main_instance.id
                        resized_values["api_property_detail_id"] = property_id
                        resized_values["super_id"] = super_id
                        db.add(resized_model(**resized_values))

        if "nearestStations" in property_data and isinstance(
            property_data["nearestStations"], list
        ):
            for station_data in property_data["nearestStations"]:
                station_values = map_data_to_model(
                    station_data, ApiPropertyDetailNearestStation
                )
                station_values["api_property_detail_id"] = property_id
                station_values["super_id"] = super_id
                station_instance = ApiPropertyDetailNearestStation(**station_values)
                db.add(station_instance)
                await db.flush()

                if "types" in station_data and isinstance(station_data["types"], list):
                    for type_name in station_data["types"]:
                        type_values = {
                            "station_id": station_instance.id,
                            "api_property_detail_id": property_id,
                            "super_id": super_id,
                            "type": type_name,
                        }
                        db.add(ApiPropertyDetailNearestStationType(**type_values))

        await db.commit()
        logger.info(f"Successfully stored property-for-sale {property_id} details.")
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
            f"Generic error storing property-for-sale {property_id}: {e}", exc_info=True
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
