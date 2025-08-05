import enum

from sqlalchemy import BigInteger, Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from .base import Base


class ScrapeEventTypeEnum(enum.Enum):
    REQUEST_RECEIVED = "REQUEST_RECEIVED"
    API_CALL_ATTEMPT = "API_CALL_ATTEMPT"
    API_CALL_SUCCESS = "API_CALL_SUCCESS"
    API_CALL_FAILURE = "API_CALL_FAILURE"
    DATA_PARSED_SUCCESS = "DATA_PARSED_SUCCESS"
    DATA_PARSED_FAILURE = "DATA_PARSED_FAILURE"
    DATA_STORED_SUCCESS = "DATA_STORED_SUCCESS"
    DATA_STORED_FAILURE = "DATA_STORED_FAILURE"


class ScrapeEvent(Base):
    __tablename__ = "scrape_events"

    id = Column(BigInteger, primary_key=True)
    super_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    rightmove_property_id = Column(BigInteger, index=True)

    event_type = Column(SAEnum(ScrapeEventTypeEnum), nullable=False, index=True)
    event_timestamp = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    source_service_name = Column(Text)
    api_endpoint_called = Column(Text)

    http_status_code = Column(Integer)
    error_code = Column(Text)
    error_message = Column(Text)

    payload = Column(JSONB)  # Stores request params or API response

    response_item_count = Column(Integer)
    response_null_item_count = Column(Integer)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
