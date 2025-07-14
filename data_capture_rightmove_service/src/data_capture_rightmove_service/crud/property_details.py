"""
CRUD operations for the property-for-sale/detail endpoint data.
"""

import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import String, Text, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from data_capture_rightmove_service.models.property_details import *
from data_capture_rightmove_service.utils.logging_config import logger
from data_capture_rightmove_service.utils.property_mapper import map_property_data


def camel_to_snake(name: str) -> str:
    """Converts a camelCase string to a snake_case string."""
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


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
    This function creates a new snapshot for each request by explicitly creating
    the parent, flushing to get the ID, and then creating all children.
    """
    property_data = data.get("data")
    if not property_data:
        return False, "API response is missing the 'data' object."

    property_id = property_data.get("id")
    if not property_id:
        return False, "Could not find 'id' in property data."

    try:
        # 1. Create and insert the main parent record
        main_values = map_property_data(property_data, ApiPropertyDetails)
        main_values["id"] = property_id
        main_values["super_id"] = super_id
        property_record = ApiPropertyDetails(**main_values)
        db.add(property_record)
        await db.flush()  # Flush to get the generated snapshot_id
        snapshot_id = property_record.snapshot_id

        # Cache for instances that have their own children
        instance_cache = {}

        # 2. Handle one-to-one relationships
        one_to_one_mapping = {
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
            "price": ApiPropertyDetailPrice,  # Corrected from "prices"
            "propertyUrls": ApiPropertyDetailPropertyUrl,
            "sharedOwnership": ApiPropertyDetailSharedOwnership,
            "staticMapImgUrls": ApiPropertyDetailStaticMapImgUrl,
            "status": ApiPropertyDetailStatus,
            "streetView": ApiPropertyDetailStreetView,
            "tenure": ApiPropertyDetailTenure,
            "text": ApiPropertyDetailText,
        }

        for api_key, model_class in one_to_one_mapping.items():
            if api_key in property_data and property_data[api_key]:
                nested_values = map_property_data(property_data[api_key], model_class)
                nested_values["api_property_snapshot_id"] = snapshot_id
                nested_values["api_property_id"] = property_id
                nested_values["super_id"] = super_id

                instance = model_class(**nested_values)
                db.add(instance)
                instance_cache[api_key] = instance

        await db.flush()  # Flush to get IDs for one-to-one children

        # 3. Handle deeply nested relationships
        if "contactInfo" in instance_cache and property_data.get("contactInfo", {}).get(
            "telephoneNumbers"
        ):
            contact_info_instance = instance_cache["contactInfo"]
            tn_data = property_data["contactInfo"]["telephoneNumbers"]
            tn_values = map_property_data(
                tn_data, ApiPropertyDetailContactInfoTelephoneNumber
            )
            tn_values.update(
                {
                    "contact_info_id": contact_info_instance.id,
                    "api_property_snapshot_id": snapshot_id,
                    "api_property_id": property_id,
                    "super_id": super_id,
                }
            )
            db.add(ApiPropertyDetailContactInfoTelephoneNumber(**tn_values))

        if "customer" in instance_cache:
            customer_instance = instance_cache["customer"]
            customer_data = property_data.get("customer", {})
            if customer_data.get("customerDescription"):
                desc_values = map_property_data(
                    customer_data["customerDescription"],
                    ApiPropertyDetailCustomerDescription,
                )
                desc_values.update(
                    {
                        "customer_id": customer_instance.id,
                        "api_property_snapshot_id": snapshot_id,
                        "api_property_id": property_id,
                        "super_id": super_id,
                    }
                )
                db.add(ApiPropertyDetailCustomerDescription(**desc_values))

        # 4. Handle one-to-many relationships
        one_to_many_mapping = {
            "images": (
                ApiPropertyDetailImage,
                ApiPropertyDetailImageResizedUrl,
                "resizedImageUrls",
                "image_id",
            ),
            "floorplans": (
                ApiPropertyDetailFloorplan,
                ApiPropertyDetailFloorplanResizedUrl,
                "resizedFloorplanUrls",
                "floorplan_id",
            ),
            "industryAffiliations": (
                ApiPropertyDetailIndustryAffiliation,
                None,
                None,
                None,
            ),
            "infoReelItems": (ApiPropertyDetailInfoReelItem, None, None, None),
            "nearestStations": (
                ApiPropertyDetailNearestStation,
                ApiPropertyDetailNearestStationType,
                "types",
                "station_id",
            ),
        }

        for api_key, (
            parent_model,
            child_model,
            child_key,
            fk_name,
        ) in one_to_many_mapping.items():
            if api_key in property_data and isinstance(property_data[api_key], list):
                for item_data in property_data[api_key]:
                    parent_values = map_property_data(item_data, parent_model)
                    parent_values.update(
                        {
                            "api_property_snapshot_id": snapshot_id,
                            "api_property_id": property_id,
                            "super_id": super_id,
                        }
                    )
                    parent_instance = parent_model(**parent_values)
                    db.add(parent_instance)

                    if child_model and child_key and fk_name:
                        await db.flush()  # Flush to get parent instance ID
                        if child_key in item_data:
                            child_data_list = item_data[child_key]
                            if not isinstance(child_data_list, list):
                                child_data_list = [
                                    child_data_list
                                ]  # Handle single object case

                            for child_data in child_data_list:
                                # Check if the child data is a simple string (like for station 'types')
                                # or a dictionary (like for 'resizedImageUrls').
                                if isinstance(child_data, str):
                                    # Manually construct the dictionary for the model
                                    child_values = {"type": child_data}
                                elif isinstance(child_data, dict):
                                    # Use the existing mapper for dictionary-based children
                                    child_values = map_property_data(
                                        child_data, child_model
                                    )
                                else:
                                    logger.warning(
                                        f"Skipping unexpected child data type in {api_key}: {type(child_data)}"
                                    )
                                    continue
                                child_values.update(
                                    {
                                        fk_name: parent_instance.id,
                                        "api_property_snapshot_id": snapshot_id,
                                        "api_property_id": property_id,
                                        "super_id": super_id,
                                    }
                                )
                                db.add(child_model(**child_values))

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
        # Find the latest snapshot for the given property ID
        stmt = (
            select(ApiPropertyDetails)
            .where(ApiPropertyDetails.id == property_id)
            .order_by(ApiPropertyDetails.created_at.desc())
            .limit(1)
            .options(
                selectinload(ApiPropertyDetails.address),
                selectinload(ApiPropertyDetails.broadband),
                selectinload(ApiPropertyDetails.price),
                selectinload(ApiPropertyDetails.customer).selectinload(
                    ApiPropertyDetailCustomer.description
                ),
                selectinload(ApiPropertyDetails.listing_history),
                selectinload(ApiPropertyDetails.living_costs),
                selectinload(ApiPropertyDetails.location),
                selectinload(ApiPropertyDetails.tenure),
                selectinload(ApiPropertyDetails.text),
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

        # Helper function to convert model to dict, handling relationships
        def to_dict(obj):
            if obj is None:
                return None
            data = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
            data.pop("_sa_instance_state", None)
            return data

        response_dict = to_dict(property_details)

        # Manually add loaded relationships to the dictionary
        response_dict["address"] = to_dict(property_details.address)
        response_dict["broadband"] = to_dict(property_details.broadband)
        response_dict["price"] = to_dict(property_details.price)

        if property_details.customer:
            response_dict["customer"] = to_dict(property_details.customer)
            if property_details.customer.description:
                response_dict["customer"]["description"] = to_dict(
                    property_details.customer.description
                )

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
            station_dict["types"] = [to_dict(t) for t in station.types]
            response_dict["nearest_stations"].append(station_dict)

        response_dict["info_reel_items"] = [
            to_dict(item) for item in property_details.info_reel_items
        ]

        # Add other one-to-one relationships
        response_dict["listing_history"] = to_dict(property_details.listing_history)
        response_dict["living_costs"] = to_dict(property_details.living_costs)
        response_dict["location"] = to_dict(property_details.location)
        response_dict["tenure"] = to_dict(property_details.tenure)
        response_dict["text"] = to_dict(property_details.text)

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
            .distinct()
            .order_by(ApiPropertyDetails.id)
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        return [row[0] for row in result.fetchall()]
    except Exception as e:
        logger.error(f"Error retrieving all property sale IDs: {str(e)}")
        return []
