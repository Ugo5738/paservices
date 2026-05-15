"""
FetcherRun model — per-attempt audit trail for V2 primitive fetcher runs.

Every call to /fetchers/run and /ai-fetchers/{name}/run writes a row.
Status lifecycle (Rolf's rule 5: interim vs final state must be visible):

  draft       — freshly recorded; this is what gets written by every run.
                A multishot loop (e.g. WF B) creates many draft rows.
  final       — the canonical winning attempt for this attempt-group.
                Promoted by the parent workflow (or an explicit primitive)
                once it decides which attempt is the verified result.
  superseded  — a draft that was eclipsed by a later attempt.
  failed      — run did not produce usable data.

`parent_run_id` groups iterations together (e.g. all of WF B's attempts for
one URL share a parent so the eventual winner can be promoted and the rest
marked superseded). Single-shot runs (WF1) leave parent_run_id NULL and
get promoted to 'final' immediately.

`kind` distinguishes which V2 path produced the row, so future scoring /
drift queries can filter cleanly:
  'coded'           — coded-fetcher path (W1, /fetchers/run)
  'ai'              — AI-fetcher path (W2, /ai-fetchers/{name}/run)
  'build_benchmark' — W3 internal: ran the freshly-built Motie scraper to
                      compare against the AI-fetcher baseline for scoring.
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


class FetcherRunStatus(str, enum.Enum):
    DRAFT = "draft"
    FINAL = "final"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class FetcherRun(Base):
    """Per-attempt audit row for V2 primitive fetcher runs."""

    __tablename__ = "fetcher_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "data_capture.fetcher_runs.id",
            name="fk_fetcher_runs_parent_run_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
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
    attempt_number = Column(Integer, nullable=False, default=1)
    status = Column(String(16), nullable=False, default=FetcherRunStatus.DRAFT.value)
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
        CheckConstraint(
            "status IN ('draft', 'final', 'superseded', 'failed')",
            name="ck_fetcher_runs_status",
        ),
        # Per-service single-use check (chunk 4 — docs/superid_principles.md
        # section 4). NULL super_ids continue to be permitted while chunk 5
        # backfills and tightens the column. PostgreSQL treats multiple NULLs
        # as distinct in UNIQUE constraints, so existing NULL rows coexist.
        UniqueConstraint("super_id", name="uq_fetcher_runs_super_id"),
        Index("ix_fetcher_runs_url", "url"),
        Index("ix_fetcher_runs_domain", "domain"),
        Index("ix_fetcher_runs_parent_run_id", "parent_run_id"),
        Index("ix_fetcher_runs_status_started", "status", "started_at"),
        Index("ix_fetcher_runs_motie_build_id", "motie_build_id"),
        {"schema": "data_capture"},
    )

    def __repr__(self) -> str:
        return (
            f"<FetcherRun(kind='{self.kind}', vendor='{self.vendor}', "
            f"attempt={self.attempt_number}, status='{self.status}', "
            f"score={self.completeness_score})>"
        )
