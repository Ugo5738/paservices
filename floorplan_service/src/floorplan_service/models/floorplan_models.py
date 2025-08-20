# floorplan_service/src/floorplan_service/models/floorplan_models.py

import enum
import uuid

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from .base import Base, SuperIdMixin


class FloorplanEventTypeEnum(enum.Enum):
    REQUEST_RECEIVED = "REQUEST_RECEIVED"
    ANALYZER_CALL_ATTEMPT = "ANALYZER_CALL_ATTEMPT"
    ANALYZER_CALL_SUCCESS = "ANALYZER_CALL_SUCCESS"
    ANALYZER_CALL_FAILURE = "ANALYZER_CALL_FAILURE"
    WEBHOOK_RECEIVED = "WEBHOOK_RECEIVED"
    DATA_STORAGE_SUCCESS = "DATA_STORAGE_SUCCESS"
    DATA_STORAGE_FAILURE = "DATA_STORAGE_FAILURE"


class FloorplanEvent(Base, SuperIdMixin):
    __tablename__ = "floorplan_events"

    id = Column(Integer, primary_key=True)
    floorplan_id = Column(String(64), index=True, nullable=True)
    event_type = Column(SAEnum(FloorplanEventTypeEnum), nullable=False, index=True)
    details = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)


class FpPropertyData(Base, SuperIdMixin):
    __tablename__ = "fp_property_data"

    id = Column(Integer, primary_key=True)
    message = Column(String(255))
    property_id = Column(String(255), index=True)
    floorplan_id = Column(String(64), index=True)
    original_url = Column(String(1024))
    analysis_urls = relationship(
        "FpAnalysisUrls",
        back_populates="fp_property_data",
        uselist=False,
        cascade="all, delete-orphan",
    )


class FpAnalysisUrls(Base, SuperIdMixin):
    __tablename__ = "fp_analysis_urls"

    id = Column(Integer, primary_key=True)
    fp_property_data_id = Column(
        Integer, ForeignKey("fp_property_data.id"), nullable=False
    )
    json_file_url = Column(String(1024), nullable=True)
    csv_url = Column(String(1024), nullable=True)
    total_area_csv_url = Column(String(1024), nullable=True)
    image_labelme_side_by_side_url = Column(String(1024), nullable=True)
    notes = Column(Text, nullable=True)

    fp_property_data = relationship("FpPropertyData", back_populates="analysis_urls")
    all_floors_csv_data = relationship(
        "FpRoomCsvData", back_populates="fp_analysis_urls", cascade="all, delete-orphan"
    )
    total_areas_csv_data = relationship(
        "FpTotalAreasCsvData",
        back_populates="fp_analysis_urls",
        cascade="all, delete-orphan",
    )


class FpRoomCsvData(Base, SuperIdMixin):
    __tablename__ = "fp_room_csv_data"

    id = Column(Integer, primary_key=True)
    fp_analysis_urls_id = Column(
        Integer, ForeignKey("fp_analysis_urls.id"), nullable=False
    )

    floor_name = Column(String(100), index=True, nullable=True)
    room_name = Column(String(100), nullable=True)
    is_segment = Column(String(50), nullable=True)
    dimensions_imperial = Column(String(100), nullable=True)
    dimensions_metric = Column(String(100), nullable=True)
    room_id = Column(Float, index=True, nullable=True)
    no_of_door = Column(Float, nullable=True)
    no_of_window = Column(Float, nullable=True)
    no_of_room_points = Column(Float, nullable=True)
    min_x_pixels = Column(Float, name="min_x_pixels_csv", nullable=True)
    min_y_pixels = Column(Float, name="min_y_pixels_csv", nullable=True)
    max_x_pixels = Column(Float, name="max_x_pixels_csv", nullable=True)
    max_y_pixels = Column(Float, name="max_y_pixels_csv", nullable=True)
    max_area_metric = Column(Float, name="max_area_metric_csv", nullable=True)
    max_area_imperial = Column(Float, name="max_area_imperial_csv", nullable=True)
    max_area_pixels = Column(Float, name="max_area_pixels_csv", nullable=True)
    actual_area_pixels = Column(Float, name="actual_area_pixels_csv", nullable=True)
    pixel_ratio = Column(Float, name="pixel_ratio_csv", nullable=True)
    scale_metric = Column(Float, name="scale_metric_csv", nullable=True)
    scale_imperial = Column(Float, name="scale_imperial_csv", nullable=True)
    calculated_sq_area_metric = Column(
        Float, name="calculated_sq_area_metric_csv", nullable=True
    )
    calculated_floor_total_sq_area_metric = Column(
        Float, name="calc_floor_total_metric_csv", nullable=True
    )
    calculated_area_imperial = Column(
        Float, name="calculated_area_imperial_csv", nullable=True
    )
    calculated_floor_total_sq_area_imperial = Column(
        Float, name="calc_floor_total_imperial_csv", nullable=True
    )

    fp_analysis_urls = relationship(
        "FpAnalysisUrls", back_populates="all_floors_csv_data"
    )


class FpTotalAreasCsvData(Base, SuperIdMixin):
    __tablename__ = "fp_total_areas_csv_data"

    id = Column(Integer, primary_key=True)
    fp_analysis_urls_id = Column(
        Integer, ForeignKey("fp_analysis_urls.id"), nullable=False
    )

    area_name = Column(String(500), nullable=True)
    square_meters = Column(Float, nullable=True)
    square_feet = Column(Float, nullable=True)
    total_floors = Column(Integer, nullable=True)
    total_named_rooms = Column(Integer, nullable=True)
    total_segments = Column(Integer, nullable=True)
    total_points = Column(Integer, nullable=True)
    total_objects = Column(Integer, nullable=True)
    total_door_objects = Column(Integer, nullable=True)
    total_window_objects = Column(Integer, nullable=True)
    total_stair_objects = Column(Integer, nullable=True)
    list_of_objects = Column(Text, nullable=True)
    total_actual_pixels = Column(Float, nullable=True)
    metric_scale = Column(Float, nullable=True)
    imperial_scale = Column(Float, nullable=True)
    input_image_tokens = Column(Integer, nullable=True)
    input_text_tokens = Column(Integer, nullable=True)
    output_text_tokens = Column(Integer, nullable=True)

    fp_analysis_urls = relationship(
        "FpAnalysisUrls", back_populates="total_areas_csv_data"
    )
