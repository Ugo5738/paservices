import csv
import uuid
from io import StringIO

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..models.floorplan_models import (
    FpAnalysisUrls,
    FpPropertyData,
    FpRoomCsvData,
    FpTotalAreasCsvData,
)
from ..schemas.floorplan_schemas import WebhookOutputData
from ..utils.helpers import safe_float, safe_int
from ..utils.logging_config import logger


async def create_initial_property_record(
    db: AsyncSession,
    super_id: uuid.UUID,
    property_id: str,
    floorplan_id: str,
    original_url: str,
) -> FpPropertyData:
    """Creates the initial FpPropertyData record before calling the analyzer."""
    new_record = FpPropertyData(
        super_id=super_id,
        property_id=property_id,
        floorplan_id=floorplan_id,
        original_url=original_url,
        message="Analysis initiated",
    )
    db.add(new_record)
    await db.flush()
    return new_record


async def update_property_with_webhook_data(
    db: AsyncSession, item_data: dict, super_id: uuid.UUID
):
    """Finds the property record by floorplan_id and updates it with the webhook data."""
    floorplan_id = item_data["floorplan_id"]

    # Find the existing record
    stmt = select(FpPropertyData).where(FpPropertyData.floorplan_id == floorplan_id)
    result = await db.execute(stmt)
    fp_property = result.scalars().first()

    if not fp_property:
        logger.error(
            f"Webhook received for unknown floorplan_id: {floorplan_id}. Cannot process."
        )
        raise ValueError(f"Floorplan ID {floorplan_id} not found.")

    # Update the main record
    fp_property.message = item_data.get("message", "Analysis complete")

    # Create child records
    all_floors_info = item_data["all_floors"]
    analysis_urls = FpAnalysisUrls(
        fp_property_data_id=fp_property.id,
        super_id=super_id,
        json_file_url=str(all_floors_info.get("json_file_url")),
        csv_url=str(all_floors_info.get("csv_url")),
        total_area_csv_url=str(all_floors_info.get("total_area_csv_url")),
        image_labelme_side_by_side_url=str(
            all_floors_info.get("image_labelme_side_by_side_url")
        ),
        notes=all_floors_info.get("notes"),
    )
    db.add(analysis_urls)
    await db.flush()

    # Process CSVs
    if analysis_urls.csv_url:
        await _process_room_csv(db, analysis_urls, super_id)
    if analysis_urls.total_area_csv_url:
        await _process_total_area_csv(db, analysis_urls, super_id)


async def download_csv_content(url: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return await response.text


async def _process_room_csv(
    db: AsyncSession, analysis_urls: FpAnalysisUrls, super_id: str
):
    """Downloads and processes the all_floors.csv file."""
    content = await download_csv_content(analysis_urls.csv_url)
    reader = csv.DictReader(StringIO(content))
    for row in reader:
        room_data = FpRoomCsvData(
            fp_analysis_urls_id=analysis_urls.id,
            super_id=super_id,
            floor_name=row.get("Floor_Name"),
            room_name=row.get("Room_Name"),
            is_segment=row.get("is_segment"),
            dimensions_imperial=row.get("dimensions_imperial"),
            dimensions_metric=row.get("dimensions_metric"),
            room_id=safe_float(row.get("Room_id")),
            no_of_door=safe_float(row.get("No_of_door")),
            no_of_window=safe_float(row.get("No_of_window")),
            no_of_room_points=safe_float(row.get("No_of_room_points")),
            min_x_pixels_csv=safe_float(row.get("Min X Pixels")),
            min_y_pixels_csv=safe_float(row.get("Min Y Pixels")),
            max_x_pixels_csv=safe_float(row.get("Max X Pixels")),
            max_y_pixels_csv=safe_float(row.get("Max Y Pixels")),
            max_area_metric_csv=safe_float(row.get("Max Area Metric")),
            max_area_imperial_csv=safe_float(row.get("Max Area Imperial")),
            max_area_pixels_csv=safe_float(row.get("Max Area Pixels")),
            actual_area_pixels_csv=safe_float(row.get("Actual Area Pixels")),
            pixel_ratio_csv=safe_float(row.get("Pixel ratio")),
            scale_metric_csv=safe_float(row.get("Scale Metric")),
            scale_imperial_csv=safe_float(row.get("Scale Imperial")),
            calculated_sq_area_metric_csv=safe_float(
                row.get("Calculated Sq Area Metric")
            ),
            calc_floor_total_metric_csv=safe_float(
                row.get("Calculated Floor Total Sq Area Metric")
            ),
            calculated_area_imperial_csv=safe_float(
                row.get("calculated_area_imperial")
            ),
            calc_floor_total_imperial_csv=safe_float(
                row.get("Calculated Floor Total Sq Area Imperial")
            ),
        )
        db.add(room_data)


async def _process_total_area_csv(
    db: AsyncSession, analysis_urls: FpAnalysisUrls, super_id: str
):
    """Downloads and processes the total_area.csv file."""
    content = await download_csv_content(analysis_urls.total_area_csv_url)
    reader = csv.DictReader(StringIO(content))
    for row in reader:
        total_data = FpTotalAreasCsvData(
            fp_analysis_urls_id=analysis_urls.id,
            super_id=super_id,
            area_name=row.get("Area Name"),
            square_meters=safe_float(row.get("Square Meters")),
            square_feet=safe_float(row.get("Square Feet")),
            total_floors=safe_int(row.get("Total Floors")),
            total_named_rooms=safe_int(row.get("Total Named Rooms")),
            total_segments=safe_int(row.get("Total Segments")),
            total_points=safe_int(row.get("Total Points")),
            total_objects=safe_int(row.get("Total Objects")),
            total_door_objects=safe_int(row.get("Total Door Objects")),
            total_window_objects=safe_int(row.get("Total Window Objects")),
            total_stair_objects=safe_int(row.get("Total Stair Objects")),
            list_of_objects=row.get("List of Objects"),
            total_actual_pixels=safe_float(row.get("Total Pixels")),
            metric_scale=safe_float(row.get("Metric Scale")),
            imperial_scale=safe_float(row.get("Imperial Scale")),
            input_image_tokens=safe_int(row.get("Input Image Tokens")),
            input_text_tokens=safe_int(row.get("Input Text Tokens")),
            output_text_tokens=safe_int(row.get("Output Text Tokens")),
        )
        db.add(total_data)
