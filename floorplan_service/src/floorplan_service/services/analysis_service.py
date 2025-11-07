# src/floorplan_service/services/analysis_service.py

import csv
import uuid
from io import StringIO
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..config import settings
from ..crud import event_crud, floorplan_crud
from ..db import AsyncSessionLocal
from ..models import (
    FloorplanEventTypeEnum,
    FpAnalysisUrls,
    FpPropertyData,
    FpRoomCsvData,
    FpTotalAreasCsvData,
)
from ..utils.helpers import convert_gif_to_jpeg_and_upload_to_s3
from ..utils.logging_config import logger
from ..utils.status_notifier import get_status_notifier


async def trigger_floorplan_analysis(
    super_id: uuid.UUID,
    property_id: str,
    floorplans_data: dict,
    callback_payload: Optional[dict] = None,
):
    """Orchestrates the initiation of the floorplan analysis."""
    notifier = get_status_notifier()
    callback_url = (
        callback_payload.get("url") if callback_payload else None  # type: ignore[union-attr]
    )
    callback_headers = (
        callback_payload.get("headers") if callback_payload else None  # type: ignore[union-attr]
    )
    total_floorplans = len(floorplans_data)
    status_context = "floorplan_analysis"
    status_results: List[Dict[str, Any]] = []
    status_data: Dict[str, Any] = {
        "property_id": property_id,
        "super_id": str(super_id),
        "floorplans": status_results,
        "total_floorplans": total_floorplans,
    }
    status_summary: Dict[str, Any] = {
        "total_floorplans": total_floorplans,
        "processed_floorplans": 0,
        "analyzer_triggered": False,
    }

    if notifier:
        await notifier.notify(
            super_id=super_id,
            status="started",
            context=status_context,
            data=status_data,
            summary=dict(status_summary),
            metadata={"callback_url": callback_url},
            webhook_url=callback_url,
            webhook_headers=callback_headers,
            property_id=property_id,
            stage="initializing",
            progress=0.0,
        )

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
                    db,
                    super_id,
                    property_id,
                    client_key,
                    original_url,
                    callback_url=callback_url,
                    callback_headers=callback_headers,
                    total_floorplans=total_floorplans,
                )

                payload_floorplans[client_key] = {
                    "url": processed_url,
                    "notes": fp_data.get("notes", ""),
                }
                status_results.append(
                    {
                        "floorplan_id": client_key,
                        "original_url": original_url,
                        "processed_url": processed_url,
                        "status": "queued",
                    }
                )
                status_summary["processed_floorplans"] = len(status_results)
            except Exception as e:
                logger.error(
                    f"Error processing floorplan URL {fp_data.get('url')}: {e}",
                    exc_info=True,
                )

        if not payload_floorplans:
            logger.warning(
                f"No valid floorplans to process for property {property_id}."
            )
            if notifier:
                await notifier.notify(
                    super_id=super_id,
                    status="failed",
                    context=status_context,
                    data=status_data,
                    summary=dict(status_summary),
                    metadata={
                        "callback_url": callback_url,
                        "error": "No valid floorplans to process.",
                    },
                    webhook_url=callback_url,
                    webhook_headers=callback_headers,
                    property_id=property_id,
                    stage="validation",
                    last_error="No valid floorplans to process.",
                )
            return

        payload = {
            "user_id": str(super_id),  # Use the super_id as the user_id
            "webhook_url": settings.FLOORPLAN_WEBHOOK_URL,
            "property_id": property_id,
            "floorplans": payload_floorplans,
        }
        logger.info(
            "Prepared analyzer payload",
            extra={
                "super_id": str(super_id),
                "property_id": property_id,
                "webhook_url": settings.FLOORPLAN_WEBHOOK_URL,
                "callback_url": callback_url,
            },
        )

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
                status_summary["analyzer_triggered"] = True
                if notifier:
                    await notifier.notify(
                        super_id=super_id,
                        status="in_progress",
                        context=status_context,
                        data=status_data,
                        summary=dict(status_summary),
                        metadata={"callback_url": callback_url},
                        webhook_url=callback_url,
                        webhook_headers=callback_headers,
                        property_id=property_id,
                        stage="analyzer_triggered",
                        progress=0.2,
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
                if notifier:
                    await notifier.notify(
                        super_id=super_id,
                        status="failed",
                        context=status_context,
                        data=status_data,
                        summary=dict(status_summary),
                        metadata={
                            "callback_url": callback_url,
                            "error": str(e),
                        },
                        webhook_url=callback_url,
                        webhook_headers=callback_headers,
                        property_id=property_id,
                        stage="analyzer_call",
                        last_error=str(e),
                    )

        await db.commit()


async def process_webhook_data_task(payload_data: dict):
    """Processes the webhook data in the background."""
    notifier = get_status_notifier()
    output_items = payload_data.get("output_data", [])
    if not output_items:
        logger.warning("Webhook payload contained no output_data.")
        return

    async with AsyncSessionLocal() as db:
        callback_url: Optional[str] = None
        callback_headers: Optional[Dict[str, str]] = None
        property_id: Optional[str] = payload_data.get("property_id")
        super_id: Optional[uuid.UUID] = None
        total_floorplans: Optional[int] = None
        status_context = "floorplan_analysis"
        status_results: List[Dict[str, Any]] = []
        failure_summary: Optional[Dict[str, Any]] = None

        for item_data in output_items:
            floorplan_id = item_data.get("floorplan_id")
            fp_property: Optional[FpPropertyData] = None
            try:
                stmt = select(FpPropertyData).where(
                    FpPropertyData.floorplan_id == floorplan_id,
                    FpPropertyData.property_id == item_data.get("property_id"),
                )
                result = await db.execute(stmt)
                fp_property = result.scalars().first()

                if not fp_property:
                    logger.error(
                        f"Webhook received for unknown floorplan_id: {floorplan_id}. Cannot process."
                    )
                    continue

                if super_id is None:
                    super_id = fp_property.super_id
                if property_id is None:
                    property_id = fp_property.property_id
                if callback_url is None:
                    callback_url = fp_property.callback_url
                if callback_headers is None and fp_property.callback_headers:
                    callback_headers = fp_property.callback_headers
                if total_floorplans is None and fp_property.total_floorplans:
                    total_floorplans = fp_property.total_floorplans

                await event_crud.log_floorplan_event(
                    db,
                    fp_property.super_id,
                    FloorplanEventTypeEnum.WEBHOOK_RECEIVED,
                    floorplan_id=floorplan_id,
                )
                await floorplan_crud.update_property_with_webhook_data(
                    db, item_data, fp_property.super_id
                )
                await event_crud.log_floorplan_event(
                    db,
                    fp_property.super_id,
                    FloorplanEventTypeEnum.DATA_STORAGE_SUCCESS,
                    floorplan_id=floorplan_id,
                )
                status_results.append(
                    {
                        "floorplan_id": floorplan_id,
                        "original_url": item_data.get("original_url"),
                        "analysis": item_data.get("all_floors", {}),
                    }
                )
                await db.commit()
            except Exception as e:
                logger.error(
                    f"Failed to process webhook item for floorplan_id {floorplan_id}: {e}",
                    exc_info=True,
                )
                failure_summary = {"error": str(e), "floorplan_id": floorplan_id}
                if "fp_property" in locals() and fp_property:
                    await event_crud.log_floorplan_event(
                        db,
                        fp_property.super_id,
                        FloorplanEventTypeEnum.DATA_STORAGE_FAILURE,
                        floorplan_id=floorplan_id,
                        error_message=str(e),
                    )
                await db.rollback()

        if notifier and super_id:
            summary_payload: Dict[str, Any] = {
                "processed_floorplans": len(status_results),
                "total_floorplans": total_floorplans or len(output_items),
            }
            if failure_summary:
                status = "failed"
                summary_payload.update(failure_summary)
            else:
                status = "completed"

            await notifier.notify(
                super_id=super_id,
                status=status,
                context=status_context,
                data={
                    "super_id": str(super_id),
                    "property_id": property_id,
                    "floorplans": status_results,
                },
                summary=summary_payload,
                metadata={
                    "callback_url": callback_url,
                    "property_id": property_id,
                },
                webhook_url=callback_url,
                webhook_headers=callback_headers,
                property_id=property_id,
                stage="completed" if status == "completed" else "webhook_processing",
                progress=1.0 if status == "completed" else None,
                last_error=failure_summary.get("error") if failure_summary else None,
            )


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
