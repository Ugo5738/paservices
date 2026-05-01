"""
AIFetcher registry model.

DB-driven registry of AI fetcher vendors. Replaces the hardcoded _AI_ADAPTERS
Python dict in ai_fetchers_router so that adding a new vendor (Gemini,
BrightData, ChatGPT, DeepSeek, ...) is a single INSERT, not a code change.

`adapter_path` is an importable target like
'data_capture_service.adapters.firecrawl.firecrawl_adapter:firecrawl_adapter'
that the ai_fetcher_registry service imports lazily.
"""

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from data_capture_service.models.base import Base


class AIFetcher(Base):
    """Vendor registry for AI fetchers (the W2 / AI-fetcher path)."""

    __tablename__ = "ai_fetchers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(64), nullable=False)
    # Importable target: "module.path:attr". The registry imports this lazily.
    adapter_path = Column(String(512), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    # Lower number = higher priority for default selection.
    priority = Column(Integer, nullable=False, default=100)
    # True for the AI fetcher used as the build-time benchmark in W3 scoring.
    is_default_baseline = Column(Boolean, nullable=False, default=False)
    config_json = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("name", name="uq_ai_fetchers_name"),
        Index("ix_ai_fetchers_enabled_priority", "enabled", "priority"),
        {"schema": "data_capture"},
    )

    def __repr__(self) -> str:
        return (
            f"<AIFetcher(name='{self.name}', enabled={self.enabled}, "
            f"priority={self.priority}, default_baseline={self.is_default_baseline})>"
        )
