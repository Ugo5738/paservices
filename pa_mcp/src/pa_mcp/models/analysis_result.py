from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB

from ..db import Base


class AnalysisResult(Base):
    """Persistent analysis workflow results keyed by super_id."""

    __tablename__ = "analysis_results"

    super_id = Column(String, primary_key=True, index=True)
    status = Column(String, nullable=True)
    remote_status = Column(String, nullable=True)
    property_url = Column(String, nullable=True)
    workflow_callback_url = Column(String, nullable=True)
    n8n_triggered = Column(Boolean, nullable=True)
    final_result = Column(JSONB, nullable=True)
    error = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "super_id": self.super_id,
            "status": self.status,
            "remote_status": self.remote_status,
            "property_url": self.property_url,
            "workflow_callback_url": self.workflow_callback_url,
            "n8n_triggered": self.n8n_triggered,
            "final_result": self.final_result,
            "error": self.error,
            "created_at": self._ts(self.created_at),
            "updated_at": self._ts(self.updated_at),
        }

    @staticmethod
    def _ts(value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None
