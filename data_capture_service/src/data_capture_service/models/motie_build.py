"""
MotieBuild model — one row per Motie build attempt.

Drives the encapsulated session+deploy state machine so n8n only polls a
single status endpoint instead of orchestrating Motie's 4-step protocol
(invoke → poll session → deploy → poll deployment) directly. Per Rolf's
rule that workflow logic belongs to n8n but adapter implementation
detail (Motie's internal protocol) belongs to the data-capture service.

State lifecycle:
  session_pending → session_running → session_complete
                                        → deploying → deployed (terminal)
                                        → session_failed (terminal)
                                        → deployment_failed (terminal)

Repair attempts chain via parent_build_id, so a failed initial build's repair
session is linked back to its origin for the audit trail.
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
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from data_capture_service.models.base import Base


class MotieBuildState(str, enum.Enum):
    """State machine values stored as plain strings in the DB."""

    SESSION_PENDING = "session_pending"
    SESSION_RUNNING = "session_running"
    SESSION_COMPLETE = "session_complete"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    SESSION_FAILED = "session_failed"
    DEPLOYMENT_FAILED = "deployment_failed"


class MotieBuildPromptKind(str, enum.Enum):
    BUILD = "build"
    REPAIR = "repair"


TERMINAL_BUILD_STATES = {
    MotieBuildState.DEPLOYED.value,
    MotieBuildState.SESSION_FAILED.value,
    MotieBuildState.DEPLOYMENT_FAILED.value,
}


class MotieBuild(Base):
    """One row per Motie build attempt (initial or repair)."""

    __tablename__ = "motie_builds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_uuid = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "data_capture.motie_scraper_projects.id",
            name="fk_motie_builds_project_uuid",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    domain = Column(String(512), nullable=False)
    url = Column(String(2048), nullable=False)
    prompt_kind = Column(
        String(16), nullable=False
    )  # 'build' | 'repair'
    state = Column(
        String(32),
        nullable=False,
        default=MotieBuildState.SESSION_PENDING.value,
    )
    session_id = Column(String(256), nullable=True)
    deployment_id = Column(String(256), nullable=True)
    api_url = Column(String(2048), nullable=True)
    attempt_number = Column(Integer, nullable=False, default=1)
    parent_build_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "data_capture.motie_builds.id",
            name="fk_motie_builds_parent_build_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    benchmark_score = Column(Float, nullable=True)
    benchmark_diff_json = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    finished_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "prompt_kind IN ('build', 'repair')",
            name="ck_motie_builds_prompt_kind",
        ),
        CheckConstraint(
            "state IN ('session_pending', 'session_running', 'session_complete', "
            "'deploying', 'deployed', 'session_failed', 'deployment_failed')",
            name="ck_motie_builds_state",
        ),
        Index("ix_motie_builds_project_uuid", "project_uuid"),
        Index("ix_motie_builds_state", "state"),
        Index("ix_motie_builds_session_id", "session_id"),
        {"schema": "data_capture"},
    )

    def is_terminal(self) -> bool:
        return self.state in TERMINAL_BUILD_STATES

    def __repr__(self) -> str:
        return (
            f"<MotieBuild(domain='{self.domain}', kind='{self.prompt_kind}', "
            f"attempt={self.attempt_number}, state='{self.state}')>"
        )
