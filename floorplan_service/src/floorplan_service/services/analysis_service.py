# src/floorplan_service/services/analysis_service.py

import csv
import uuid
from io import StringIO

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..crud import event_crud, floorplan_crud
from ..db import AsyncSessionLocal
from ..models.floorplan_models import (
    FloorplanEventTypeEnum,
    FpAnalysisUrls,
    FpPropertyData,
    FpRoomCsvData,
    FpTotalAreasCsvData,
)
from ..utils.helpers import convert_gif_to_jpeg_and_upload_to_s3
from ..utils.logging_config import logger


async def trigger_floorplan_analysis(
    super_id: uuid.UUID, property_id: str, floorplans_data: dict
):
    """Orchestrates the initiation of the floorplan analysis."""
    async with AsyncSessionLocal() as db:
        await event_crud.log_floorplan_event(
            db,
            super_id,
            FloorplanEventTypeEnum.REQUEST_RECEIVED,
            details={
                "property_id": property_id,
                "floorplan_count": len(floorplans_data),
            },
        )

        payload_floorplans = {}
        for client_key, fp_data in floorplans_data.items():
            try:
                original_url = str(fp_data["url"])
                processed_url = convert_gif_to_jpeg_and_upload_to_s3(
                    super_id, original_url, property_id
                )

                # Create initial DB record to store the super_id association
                await floorplan_crud.create_initial_property_record(
                    db, super_id, property_id, client_key, original_url
                )

                payload_floorplans[client_key] = {
                    "url": processed_url,
                    "notes": fp_data.get("notes", ""),
                }
            except Exception as e:
                logger.error(
                    f"Error processing floorplan URL {fp_data.get('url')}: {e}",
                    exc_info=True,
                )

        if not payload_floorplans:
            logger.warning(
                f"No valid floorplans to process for property {property_id}."
            )
            return

        payload = {
            "user_id": str(super_id),  # Use the super_id as the user_id
            "webhook_url": settings.FLOORPLAN_WEBHOOK_URL,
            "property_id": property_id,
            "floorplans": payload_floorplans,
        }

        await event_crud.log_floorplan_event(
            db,
            super_id,
            FloorplanEventTypeEnum.ANALYZER_CALL_ATTEMPT,
            details={
                "analyzer_url": settings.FLOORPLAN_ANALYZER_URL,
                "payload_keys": list(payload.keys()),
            },
        )

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    settings.FLOORPLAN_ANALYZER_URL, json=payload, timeout=60.0
                )
                response.raise_for_status()
                await event_crud.log_floorplan_event(
                    db, super_id, FloorplanEventTypeEnum.ANALYZER_CALL_SUCCESS
                )
                logger.info(
                    f"Successfully initiated analysis for property {property_id} with super_id {super_id}"
                )
            except httpx.RequestError as e:
                await event_crud.log_floorplan_event(
                    db,
                    super_id,
                    FloorplanEventTypeEnum.ANALYZER_CALL_FAILURE,
                    error_message=str(e),
                )
                logger.error(
                    f"Failed to call analyzer API for property {property_id}: {e}"
                )

        await db.commit()


async def process_webhook_data_task(payload_data: dict):
    """Processes the webhook data in the background."""
    async with AsyncSessionLocal() as db:
        for item_data in payload_data.get("output_data", []):
            floorplan_id = item_data.get("floorplan_id")
            try:
                # Find the super_id from the initial record
                stmt = select(FpPropertyData.super_id).where(
                    FpPropertyData.floorplan_id == floorplan_id
                )
                result = await db.execute(stmt)
                super_id = result.scalars().first()

                if not super_id:
                    logger.error(
                        f"Webhook received for unknown floorplan_id: {floorplan_id}. Cannot process."
                    )
                    continue

                await event_crud.log_floorplan_event(
                    db,
                    super_id,
                    FloorplanEventTypeEnum.WEBHOOK_RECEIVED,
                    floorplan_id=floorplan_id,
                )
                await floorplan_crud.update_property_with_webhook_data(
                    db, item_data, super_id
                )
                await event_crud.log_floorplan_event(
                    db,
                    super_id,
                    FloorplanEventTypeEnum.DATA_STORAGE_SUCCESS,
                    floorplan_id=floorplan_id,
                )
                await db.commit()
            except Exception as e:
                logger.error(
                    f"Failed to process webhook item for floorplan_id {floorplan_id}: {e}",
                    exc_info=True,
                )
                if "super_id" in locals() and super_id:
                    await event_crud.log_floorplan_event(
                        db,
                        super_id,
                        FloorplanEventTypeEnum.DATA_STORAGE_FAILURE,
                        floorplan_id=floorplan_id,
                        error_message=str(e),
                    )
                await db.rollback()


# async def _process_single_floorplan_item(
#     db: AsyncSession, item_data: dict, super_id: str, payload_data: dict
# ):
#     """Processes and stores a single floorplan item from the webhook."""
#     # 1. Create FpPropertyData
#     fp_property = FpPropertyData(
#         message=payload_data.get("message", "Processed"),
#         property_id=item_data["property_id"],
#         super_id=super_id,
#         floorplan_id=item_data["floorplan_id"],
#         original_url=item_data["original_url"],
#     )
#     db.add(fp_property)
#     await db.flush()

#     # 2. Create FpAnalysisUrls
#     all_floors_info = item_data["all_floors"]
#     analysis_urls = FpAnalysisUrls(
#         fp_property_data_id=fp_property.id,
#         super_id=super_id,
#         json_file_url=str(all_floors_info.get("json_file_url")),
#         csv_url=str(all_floors_info.get("csv_url")),
#         total_area_csv_url=str(all_floors_info.get("total_area_csv_url")),
#         image_labelme_side_by_side_url=str(
#             all_floors_info.get("image_labelme_side_by_side_url")
#         ),
#         notes=all_floors_info.get("notes"),
#     )
#     db.add(analysis_urls)
#     await db.flush()

#     # 3. Process CSVs
#     if analysis_urls.csv_url:
#         await _process_room_csv(db, analysis_urls, super_id)
#     if analysis_urls.total_area_csv_url:
#         await _process_total_area_csv(db, analysis_urls, super_id)
