from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..db import Base


class AnalysisUpdate(Base):
    """Append-only workflow/service update events keyed by super_id."""

    __tablename__ = "analysis_updates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    super_id = Column(String, nullable=False, index=True)
    status = Column(String, nullable=True)
    context = Column(String, nullable=True)
    event_timestamp = Column(DateTime(timezone=True), nullable=True)
    summary = Column(JSONB, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True)
    data_location = Column(String, nullable=True)
    final_result = Column(JSONB, nullable=True)
    error = Column(JSONB, nullable=True)
    raw_payload = Column(JSONB, nullable=False)
    received_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "super_id": self.super_id,
            "status": self.status,
            "context": self.context,
            "event_timestamp": self._ts(self.event_timestamp),
            "received_at": self._ts(self.received_at),
            "summary": self.summary,
            "metadata": self.metadata_,
            "data_location": self.data_location,
            "final_result": self.final_result,
            "error": self.error,
            "raw_payload": self.raw_payload,
        }

    @staticmethod
    def _ts(value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None
