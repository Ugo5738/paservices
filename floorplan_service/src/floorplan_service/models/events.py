"""
Event models for the Floorplan service.
"""

import enum

from sqlalchemy import Column, Enum as SAEnum, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

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
