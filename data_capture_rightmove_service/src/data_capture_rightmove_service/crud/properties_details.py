"""
CRUD operations for the properties_details endpoint data.
"""

import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_rightmove_service.models.properties_details_v2 import *
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
    Takes a dictionary with camelCase keys (from an API) and maps it to
    a dictionary with snake_case keys suitable for a SQLAlchemy model.
    It only includes keys that are actual attributes of the model.

    Automatically converts dictionary values to JSON strings for TEXT/String columns.
    """
    snake_case_data = {}
    valid_model_keys = {c.name: c for c in model_class.__table__.columns}

    for key, value in data.items():
        snake_key = camel_to_snake(key)

        # Handle special cases where API name doesn't map cleanly
        if model_class == ApiPropertiesDetailsV2 and snake_key == "identifier":
            snake_key = "id"
        if model_class == ApiPropertiesDetailsV2Price and snake_key == "primary":
            snake_key = "primary_price"
        if model_class == ApiPropertiesDetailsV2Price and snake_key == "secondary":
            snake_key = "secondary_price"
        if model_class == ApiPropertiesDetailsV2Brochure:
            if snake_key == "brochures":  # The API nests the list under 'brochures'
                snake_key = "items"

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


async def store_properties_details(
    db: AsyncSession, data: Dict[str, Any], super_id: uuid.UUID
) -> Tuple[bool, str]:
    """
    Store property details data from the properties/details v2 API.
    This function creates a new snapshot for each request.
    """
    property_data = data.get("data")
    if not property_data:
        return False, "API response is missing the 'data' object."

    property_id = property_data.get("identifier")
    if not property_id:
        return False, "Could not find 'identifier' in property data."

    try:
        # 1. Main object
        main_values = map_property_data(property_data, ApiPropertiesDetailsV2)
        main_values["id"] = property_id
        main_values["super_id"] = super_id
        property_record = ApiPropertiesDetailsV2(**main_values)
        db.add(property_record)
        await db.flush()  # Flush to get snapshot_id for relationships
        snapshot_id = property_record.snapshot_id

        # 2. Nested one-to-one relationships
        one_to_one_models = {
            "misInfo": ApiPropertiesDetailsV2Misinfo,
            "status": ApiPropertiesDetailsV2Status,
            "stampDutyCalculator": ApiPropertiesDetailsV2StampDuty,
            "branch": ApiPropertiesDetailsV2Branch,
            "price": ApiPropertiesDetailsV2Price,
            "localPropertyTax": ApiPropertiesDetailsV2LocalTax,
            "salesInfo": ApiPropertiesDetailsV2SalesInfo,
            "size": ApiPropertiesDetailsV2Size,
            "mortgageCalculator": ApiPropertiesDetailsV2Mortgage,
            "analyticsInfo": ApiPropertiesDetailsV2AnalyticsInfo,
            "features": ApiPropertiesDetailsV2Features,
            "brochure": ApiPropertiesDetailsV2Brochure,
            "location": ApiPropertiesDetailsV2Location,
        }

        # Store instances to use their generated IDs for nested children
        instance_cache = {}

        for api_key, model_class in one_to_one_models.items():
            if api_key in property_data and property_data[api_key]:
                nested_data = property_data[api_key]
                nested_values = map_property_data(nested_data, model_class)
                nested_values["api_property_snapshot_id"] = snapshot_id
                nested_values["api_property_id"] = property_id
                nested_values["super_id"] = super_id

                instance = model_class(**nested_values)
                db.add(instance)
                instance_cache[api_key] = instance

        # Flush to get IDs for nested relationships
        await db.flush()

        # 3. Deeply nested relationships (children of children)
        if "features" in instance_cache:
            features_instance = instance_cache["features"]
            features_data = property_data.get("features", {})

            if "risks" in features_data and features_data["risks"]:
                risk_values = map_property_data(
                    features_data["risks"], ApiPropertiesDetailsV2FeatureRisks
                )
                # --- FIX: Use correct keyword 'feature_id' ---
                risk_values["feature_id"] = features_instance.id
                risk_values["api_property_snapshot_id"] = snapshot_id
                risk_values["api_property_id"] = property_id
                risk_values["super_id"] = super_id
                db.add(ApiPropertiesDetailsV2FeatureRisks(**risk_values))

            if "obligations" in features_data and features_data["obligations"]:
                obligation_values = map_property_data(
                    features_data["obligations"],
                    ApiPropertiesDetailsV2FeatureObligations,
                )
                # --- FIX: Use correct keyword 'feature_id' ---
                obligation_values["feature_id"] = features_instance.id
                obligation_values["api_property_snapshot_id"] = snapshot_id
                obligation_values["api_property_id"] = property_id
                obligation_values["super_id"] = super_id
                db.add(ApiPropertiesDetailsV2FeatureObligations(**obligation_values))

        if "location" in instance_cache:
            location_instance = instance_cache["location"]
            location_data = property_data.get("location", {})
            if "streetView" in location_data and location_data["streetView"]:
                streetview_values = map_property_data(
                    location_data["streetView"],
                    ApiPropertiesDetailsV2LocationStreetview,
                )
                # --- FIX: Use correct keyword 'location_id' ---
                streetview_values["location_id"] = location_instance.id
                streetview_values["api_property_snapshot_id"] = snapshot_id
                streetview_values["api_property_id"] = property_id
                streetview_values["super_id"] = super_id
                db.add(ApiPropertiesDetailsV2LocationStreetview(**streetview_values))

        if "brochure" in instance_cache:
            brochure_instance = instance_cache["brochure"]
            brochure_data = property_data.get("brochure", {})
            if "brochures" in brochure_data and isinstance(
                brochure_data["brochures"], list
            ):
                for item_data in brochure_data["brochures"]:
                    item_values = map_property_data(
                        item_data, ApiPropertiesDetailsV2BrochureItem
                    )
                    # --- FIX: Use correct keyword 'brochure_id' ---
                    item_values["brochure_id"] = brochure_instance.id
                    item_values["api_property_snapshot_id"] = snapshot_id
                    item_values["api_property_id"] = property_id
                    item_values["super_id"] = super_id
                    db.add(ApiPropertiesDetailsV2BrochureItem(**item_values))

        # 4. Handle one-to-many relationships
        one_to_many_models = {
            "stations": ApiPropertiesDetailsV2Station,
            "photos": ApiPropertiesDetailsV2Photo,
            "epcs": ApiPropertiesDetailsV2Epc,
            "floorplans": ApiPropertiesDetailsV2Floorplan,
        }

        for api_key, model_class in one_to_many_models.items():
            if api_key in property_data and isinstance(property_data[api_key], list):
                for item_data in property_data[api_key]:
                    item_values = map_property_data(item_data, model_class)
                    item_values["api_property_snapshot_id"] = snapshot_id
                    item_values["api_property_id"] = property_id
                    item_values["super_id"] = super_id
                    db.add(model_class(**item_values))

        logger.info(f"Successfully prepared snapshot for property {property_id}.")
        return True, f"Successfully stored property {property_id} details."

    except IntegrityError as e:
        await db.rollback()
        logger.error(
            f"DB Integrity Error for property {property_id}: {e.orig}", exc_info=True
        )
        return False, f"Database integrity error: {e.orig}"
    except Exception as e:
        await db.rollback()
        logger.error(f"Error storing property {property_id}: {e}", exc_info=True)
        return False, f"Error storing property details: {e}"


async def get_property_details_by_id(
    db: AsyncSession, property_id: int
) -> Optional[Dict[str, Any]]:
    """
    Get property details by ID with all related information.

    Args:
        db: Database session
        property_id: Rightmove property ID

    Returns:
        Optional[Dict[str, Any]]: Property details or None if not found
    """
    try:
        # Query the main property details
        result = await db.execute(
            select(ApiPropertiesDetailsV2).where(
                ApiPropertiesDetailsV2.id == property_id
            )
        )
        property_details = result.scalar_one_or_none()

        if not property_details:
            return None

        # Get branch information
        branch_result = await db.execute(
            select(ApiPropertiesDetailsV2Branch).where(
                ApiPropertiesDetailsV2Branch.api_property_id == property_id
            )
        )
        branch = branch_result.scalar_one_or_none()

        # Get price information
        price_result = await db.execute(
            select(ApiPropertiesDetailsV2Price).where(
                ApiPropertiesDetailsV2Price.api_property_id == property_id
            )
        )
        price = price_result.scalar_one_or_none()

        # Get location information
        location_result = await db.execute(
            select(ApiPropertiesDetailsV2Location).where(
                ApiPropertiesDetailsV2Location.api_property_id == property_id
            )
        )
        location = location_result.scalar_one_or_none()

        # Get images
        images_result = await db.execute(
            select(ApiPropertiesDetailsV2Photo).where(
                ApiPropertiesDetailsV2Photo.api_property_id == property_id
            )
        )
        images = images_result.scalars().all()

        # Get floorplans
        floorplans_result = await db.execute(
            select(ApiPropertiesDetailsV2Floorplan).where(
                ApiPropertiesDetailsV2Floorplan.api_property_id == property_id
            )
        )
        floorplans = floorplans_result.scalars().all()

        # Get nearest stations
        stations_result = await db.execute(
            select(ApiPropertiesDetailsV2Station).where(
                ApiPropertiesDetailsV2Station.api_property_id == property_id
            )
        )
        stations = stations_result.scalars().all()

        # Convert database models to dictionary
        property_dict = {
            "id": property_details.id,
            "super_id": str(property_details.super_id),
            "transaction_type": property_details.transaction_type,
            "channel": property_details.channel,
            "bedrooms": property_details.bedrooms,
            "bathrooms": property_details.bathrooms,
            "address": property_details.address,
            "contact_method": property_details.contact_method,
            "property_disclaimer": property_details.property_disclaimer,
            "property_phrase": property_details.property_phrase,
            "full_description": property_details.full_description,
            "listing_update_reason": property_details.listing_update_reason,
            "property_url": property_details.property_url,
            "school_checker_url": property_details.school_checker_url,
            "lettings_info": property_details.lettings_info,
            "property_display_type": property_details.property_display_type,
            "telephone_number": property_details.telephone_number,
            "saved": property_details.saved,
            "sold_prices_url": property_details.sold_prices_url,
            "market_info_url": property_details.market_info_url,
            "note": property_details.note,
            "link_to_glossary": property_details.link_to_glossary,
            "enquired_timestamp": property_details.enquired_timestamp,
            "key_features": property_details.key_features,
            "tags": property_details.tags,
            "virtual_tours": property_details.virtual_tours,
            "branch": branch.__dict__ if branch else None,
            "price": price.__dict__ if price else None,
            "location": location.__dict__ if location else None,
            "images": [img.__dict__ for img in images] if images else [],
            "floorplans": [fp.__dict__ for fp in floorplans] if floorplans else [],
            "nearest_stations": [ns.__dict__ for ns in stations] if stations else [],
            "created_at": property_details.created_at.isoformat(),
            "updated_at": property_details.updated_at.isoformat(),
        }

        # Clean up the dictionaries to remove SQLAlchemy instance state
        for dict_key in ["branch", "price", "location"]:
            if property_dict[dict_key]:
                property_dict[dict_key].pop("_sa_instance_state", None)

        for items_key in ["images", "floorplans", "nearest_stations"]:
            for item in property_dict[items_key]:
                item.pop("_sa_instance_state", None)

        return property_dict

    except Exception as e:
        logger.error(f"Error retrieving property details: {str(e)}")
        return None


async def get_all_property_ids(
    db: AsyncSession, limit: int = 1000, offset: int = 0
) -> List[int]:
    """
    Get all property IDs stored in the database.

    Args:
        db: Database session
        limit: Maximum number of IDs to return
        offset: Offset for pagination

    Returns:
        List[int]: List of property IDs
    """
    try:
        result = await db.execute(
            select(ApiPropertiesDetailsV2.id)
            .order_by(ApiPropertiesDetailsV2.id)
            .limit(limit)
            .offset(offset)
        )
        return [row[0] for row in result.fetchall()]
    except Exception as e:
        logger.error(f"Error retrieving all property IDs: {str(e)}")
        return []
