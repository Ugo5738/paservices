# src/data_capture_rightmove_service/crud/property_search.py

import uuid
from typing import Any, Dict, List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_rightmove_service.models.property_for_sale import (
    PropertyDisplayPrice,
    PropertyImage,
    PropertyListing,
)
from data_capture_rightmove_service.utils.logging_config import logger


def flatten_and_prepare(
    property_data: Dict[str, Any], super_id: uuid.UUID
) -> Dict[str, Any]:
    """Flattens the nested JSON and prepares it for the PropertyListing model."""
    flat_data = {
        "api_source_endpoint": "/buy/property-for-sale",
        "super_id": super_id,
    }

    for key, value in property_data.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                flat_data[f"{key}_{sub_key}"] = sub_value
        elif key not in ["displayPrices", "images", "keywords", "lozengeModel"]:
            flat_data[key] = value
        else:
            flat_data[key] = value

    # Rename keys to match model attributes
    key_mappings = {
        "lozengeModel_matchingLozenges": "lozenge_model_matching_lozenges_json",
        "keywords": "keywords_json",
        "customer_buildToRentBenefits": "customer_build_to_rent_benefits_json",
    }
    for old_key, new_key in key_mappings.items():
        if old_key in flat_data:
            flat_data[new_key] = flat_data.pop(old_key)

    # Filter for keys that exist in the PropertyListing model
    listing_columns = {c.name for c in PropertyListing.__table__.columns}
    return {k: v for k, v in flat_data.items() if k in listing_columns}


async def store_property_search_results(
    db: AsyncSession,
    properties: List[Dict[str, Any]],
    super_id: uuid.UUID,
    update_existing: bool = False,  # Parameter to control behavior
) -> Tuple[int, int]:
    """
    Parses a list of properties and stores them in the database.

    By default, this uses an "insert-only" approach, creating a new historical
    snapshot for every property fetched.

    If `update_existing` is True, it will perform an "upsert" instead.

    Args:
        db: The async database session.
        properties: A list of property data dictionaries from the API.
        super_id: The tracking UUID for this batch operation.
        update_existing: If True, update records with the same ID. If False, create new ones.

    Returns:
        A tuple of (successful_count, failed_count).
    """
    successful_count = 0
    failed_count = 0

    if not properties:
        return 0, 0

    if update_existing:
        logger.info("Using UPSERT mode: Existing property records will be updated.")
    else:
        logger.info("Using INSERT-ONLY mode: New snapshot records will be created.")

    for prop_data in properties:
        property_id = prop_data.get("id")
        if not property_id:
            failed_count += 1
            logger.warning("Skipping property with no ID.")
            continue

        try:
            # 1. Prepare main listing data
            prepared_data = flatten_and_prepare(prop_data, super_id)

            if update_existing:
                # --- UPSERT LOGIC (Optional) ---
                from sqlalchemy.dialects.postgresql import insert

                stmt = (
                    insert(PropertyListing)
                    .values(**prepared_data)
                    .on_conflict_do_update(index_elements=["id"], set_=prepared_data)
                )
                await db.execute(stmt)
                # (You would also need to clear and re-insert child records here)
            else:
                # --- INSERT-ONLY LOGIC ---
                # Create a new parent record every time.
                property_record = PropertyListing(**prepared_data)
                db.add(property_record)
                await db.flush()  # Flush to get the auto-generated snapshot_id

                # Insert new child records linked to the new snapshot_id
                snapshot_id = property_record.snapshot_id
                if (
                    "propertyImages" in prop_data
                    and "images" in prop_data["propertyImages"]
                ):
                    for image in prop_data["propertyImages"]["images"]:
                        # Map camelCase API fields to snake_case model fields
                        image_data = {
                            "caption": image.get("caption"),
                            "src_url": image.get("srcUrl"),  # Map srcUrl to src_url
                            "url": image.get("url")
                        }
                        
                        db.add(
                            PropertyImage(
                                property_listing_snapshot_id=snapshot_id,
                                super_id=super_id,
                                **image_data
                            )
                        )

                if "price" in prop_data and "displayPrices" in prop_data["price"]:
                    for price in prop_data["price"]["displayPrices"]:
                        # Map camelCase API fields to snake_case model fields
                        price_data = {
                            "display_price": price.get("displayPrice"),  # Map displayPrice to display_price
                            "display_price_qualifier": price.get("displayPriceQualifier")
                        }
                        
                        db.add(
                            PropertyDisplayPrice(
                                property_listing_snapshot_id=snapshot_id,
                                super_id=super_id,
                                **price_data
                            )
                        )

            successful_count += 1
        except Exception as e:
            failed_count += 1
            logger.error(
                f"Failed to store property search result {property_id}: {e}",
                exc_info=True,
            )
            await db.rollback()

    return successful_count, failed_count
