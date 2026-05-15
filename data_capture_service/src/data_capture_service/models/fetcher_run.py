"""
FetcherRun model — per-use audit row for V2 primitive fetcher runs.

Every call to /fetchers/run, /ai-fetchers/{name}/run, and the
Fetcher Build benchmark path writes exactly one row. After chunk 5 of
the V2 SuperID rollout, rows are immutable: once inserted they are never
mutated and never deleted. Success / failure is signalled by
`error_message IS NULL` — a derived predicate, never a mutated column.

Iteration / supersession / fallback chains live in the SuperID Metadata
store (activity records + link records on super_id_service), NOT in this
table. See docs/data_capture_v2_id_and_data_flow.md for the worked
example and docs/superid_principles.md sections 5 and 9 for the
rationale ("Mistake: encoding ordering or sequence in a field on the
SuperID").

`kind` distinguishes which V2 path produced the row so downstream
scoring / drift queries can filter cleanly:

  'coded'           — coded-fetcher path (WF DC A CF, /fetchers/run)
  'ai'              — AI-fetcher path (WF DC B AIF, /ai-fetchers/{name}/run)
  'build_benchmark' — WF DC 2 Build CF internal: ran the freshly-built
                      Motie scraper to compare against the AI-fetcher
                      baseline for scoring.

NOTE: chunk 5 will be re-named to `fetcher_type` in chunk 6 alongside
the broader vocabulary cleanup.
"""

import enum
import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from data_capture_service.models.base import Base


class FetcherRunKind(str, enum.Enum):
    CODED = "coded"
    AI = "ai"
    BUILD_BENCHMARK = "build_benchmark"


class FetcherRun(Base):
    """Per-use audit row for V2 primitive fetcher runs. Immutable, append-only."""

    __tablename__ = "fetcher_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    super_id = Column(UUID(as_uuid=True), nullable=True)
    kind = Column(String(16), nullable=False)
    vendor = Column(String(64), nullable=False)
    fetcher_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "data_capture.fetchers.id",
            name="fk_fetcher_runs_fetcher_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    ai_fetcher_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "data_capture.ai_fetchers.id",
            name="fk_fetcher_runs_ai_fetcher_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    motie_build_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "data_capture.motie_builds.id",
            name="fk_fetcher_runs_motie_build_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    url = Column(String(2048), nullable=False)
    domain = Column(String(512), nullable=False)
    completeness_score = Column(Float, nullable=True)
    payload_json = Column(JSONB, nullable=True)
    fields_json = Column(JSONB, nullable=True)
    field_presence_json = Column(JSONB, nullable=True)
    missing_fields_json = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    metadata_json = Column(JSONB, nullable=True)
    started_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('coded', 'ai', 'build_benchmark')",
            name="ck_fetcher_runs_kind",
        ),
        # Per-service single-use check (chunk 4 — docs/superid_principles.md
        # section 4). NULL super_ids continue to be permitted; Postgres treats
        # multiple NULLs as distinct in UNIQUE constraints.
        UniqueConstraint("super_id", name="uq_fetcher_runs_super_id"),
        Index("ix_fetcher_runs_url", "url"),
        Index("ix_fetcher_runs_domain", "domain"),
        Index("ix_fetcher_runs_motie_build_id", "motie_build_id"),
        {"schema": "data_capture"},
    )

    @property
    def succeeded(self) -> bool:
        """Derived: a fetcher run is successful when no error was recorded."""
        return self.error_message is None

    def __repr__(self) -> str:
        outcome = "success" if self.succeeded else "failed"
        return (
            f"<FetcherRun(kind='{self.kind}', vendor='{self.vendor}', "
            f"outcome='{outcome}', score={self.completeness_score})>"
        )
