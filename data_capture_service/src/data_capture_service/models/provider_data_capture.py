"""
ProviderDataCapture model — adapter registry for managing available data_captures.
"""

import uuid

from sqlalchemy import Boolean, Column, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


class ProviderDataCapture(Base):
    """Registry of available data_capture adapters and their configuration."""

    __tablename__ = "provider_data_captures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(128), nullable=False, unique=True, index=True)
    display_name = Column(String(256), nullable=False)
    provider_type = Column(String(128), nullable=False)
    supported_domains = Column(JSONB, nullable=True)  # List of domain patterns
    is_enabled = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=0)
    config_json = Column(JSONB, nullable=True)
