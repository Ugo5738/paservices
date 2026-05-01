"""Add ai_fetchers, fetcher_runs, motie_builds tables; build_score on fetchers.

Revision ID: h9f5e3a8b1c2
Revises: g8e4d2f5h6c7
Create Date: 2026-05-01

V2 architectural alignment:

- ai_fetchers: DB-driven registry of AI fetcher vendors (Firecrawl today, Gemini /
  BrightData / etc. tomorrow). Replaces the hardcoded _AI_ADAPTERS Python dict in
  ai_fetchers_router. Vendor-agnostic by construction (rule 3).

- fetcher_runs: per-attempt audit trail for V2 primitive runs. Every call to
  /fetchers/run and /ai-fetchers/{name}/run writes a row. Status lifecycle
  draft → final / superseded / failed gives WF B's multishot loop and W3's
  repair loop visible interim history (rule 5).

- motie_builds: tracks one row per Motie build attempt (initial or repair).
  Drives the encapsulated session+deploy state machine so n8n only polls a
  single status endpoint, not the 4-step Motie protocol (rule 7). Also the
  audit chain for repair attempts via parent_build_id.

- fetchers.build_score: stores the AI-fetcher-vs-coded-fetcher score at
  registration time, for future drift comparison.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "h9f5e3a8b1c2"
down_revision: Union[str, None] = "g8e4d2f5h6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- ai_fetchers (vendor-agnostic AI fetcher registry) ---
    op.create_table(
        "ai_fetchers",
        sa.Column(
            "id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column(
            "adapter_path",
            sa.String(512),
            nullable=False,
            comment=(
                "Importable adapter target as 'module.path:attr', e.g. "
                "'data_capture_service.adapters.firecrawl.firecrawl_adapter:firecrawl_adapter'. "
                "ai_fetcher_registry imports this lazily."
            ),
        ),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("100"),
            comment="Lower number = higher priority for default selection.",
        ),
        sa.Column(
            "is_default_baseline",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment=(
                "True for the AI fetcher used as the build-time benchmark in W3 "
                "scoring. Exactly one row should be true at a time (enforced by "
                "partial unique index)."
            ),
        ),
        sa.Column(
            "config_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Vendor-specific config (timeout overrides, model name, etc.).",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_fetchers"),
        sa.UniqueConstraint("name", name="uq_ai_fetchers_name"),
        schema="data_capture",
    )

    # Only one default-baseline AI fetcher at a time.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_ai_fetchers_default_baseline
        ON data_capture.ai_fetchers (is_default_baseline)
        WHERE is_default_baseline = true;
        """
    )
    op.create_index(
        "ix_ai_fetchers_enabled_priority",
        "ai_fetchers",
        ["enabled", "priority"],
        schema="data_capture",
    )

    # Seed Firecrawl as the only registered AI fetcher today, marked as the
    # default baseline used for build-time scoring (rule 3 lives in the
    # config — code reads from this table, never hardcodes "firecrawl").
    op.execute(
        """
        INSERT INTO data_capture.ai_fetchers
            (name, adapter_path, enabled, priority, is_default_baseline, config_json)
        VALUES (
            'firecrawl',
            'data_capture_service.adapters.firecrawl.firecrawl_adapter:firecrawl_adapter',
            true,
            10,
            true,
            '{}'::jsonb
        )
        ON CONFLICT (name) DO NOTHING;
        """
    )

    # --- fetchers.build_score (score recorded at registration) ---
    op.add_column(
        "fetchers",
        sa.Column(
            "build_score",
            sa.Float(),
            nullable=True,
            comment=(
                "Completeness score (0-1) computed at build/publish time, "
                "comparing the new coded fetcher's output against the AI "
                "fetcher baseline. Used as the reference point for future "
                "drift detection."
            ),
        ),
        schema="data_capture",
    )
    op.add_column(
        "fetchers",
        sa.Column(
            "build_scored_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema="data_capture",
    )

    # --- motie_builds (one row per build attempt, encapsulates 4-step protocol) ---
    op.create_table(
        "motie_builds",
        sa.Column(
            "id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("project_uuid", sa.UUID(), nullable=False),
        sa.Column("domain", sa.String(512), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column(
            "prompt_kind",
            sa.String(16),
            nullable=False,
            comment="'build' (initial) | 'repair' (targeted at existing project code).",
        ),
        sa.Column(
            "state",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'session_pending'"),
            comment=(
                "State machine: session_pending → session_running → session_complete "
                "→ deploying → deployed (terminal) | session_failed | "
                "deployment_failed (terminal)."
            ),
        ),
        sa.Column("session_id", sa.String(256), nullable=True),
        sa.Column("deployment_id", sa.String(256), nullable=True),
        sa.Column("api_url", sa.String(2048), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("parent_build_id", sa.UUID(), nullable=True),
        sa.Column(
            "benchmark_score",
            sa.Float(),
            nullable=True,
            comment="Score after run-and-compare against AI fetcher baseline.",
        ),
        sa.Column("benchmark_diff_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_motie_builds"),
        sa.ForeignKeyConstraint(
            ["project_uuid"],
            ["data_capture.motie_scraper_projects.id"],
            name="fk_motie_builds_project_uuid",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_build_id"],
            ["data_capture.motie_builds.id"],
            name="fk_motie_builds_parent_build_id",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "prompt_kind IN ('build', 'repair')",
            name="ck_motie_builds_prompt_kind",
        ),
        sa.CheckConstraint(
            "state IN ('session_pending', 'session_running', 'session_complete', "
            "'deploying', 'deployed', 'session_failed', 'deployment_failed')",
            name="ck_motie_builds_state",
        ),
        schema="data_capture",
    )
    op.create_index(
        "ix_motie_builds_project_uuid",
        "motie_builds",
        ["project_uuid"],
        schema="data_capture",
    )
    op.create_index(
        "ix_motie_builds_state",
        "motie_builds",
        ["state"],
        schema="data_capture",
    )
    op.create_index(
        "ix_motie_builds_session_id",
        "motie_builds",
        ["session_id"],
        schema="data_capture",
    )

    # --- fetcher_runs (per-attempt audit trail for V2 primitives) ---
    op.create_table(
        "fetcher_runs",
        sa.Column(
            "id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "parent_run_id",
            sa.UUID(),
            nullable=True,
            comment=(
                "Groups multishot iterations together. WF B's repeated AI fetcher "
                "attempts share a parent_run_id so the eventual winner can be "
                "promoted to status='final' and the rest to 'superseded'."
            ),
        ),
        sa.Column("super_id", sa.UUID(), nullable=True),
        sa.Column(
            "kind",
            sa.String(16),
            nullable=False,
            comment="'coded' (W1 path) | 'ai' (W2 path) | 'build_benchmark' (W3 scoring).",
        ),
        sa.Column(
            "vendor",
            sa.String(64),
            nullable=False,
            comment="Vendor name as registered ('motie', 'firecrawl', 'rightmove_proxy', ...).",
        ),
        sa.Column("fetcher_id", sa.UUID(), nullable=True),
        sa.Column("ai_fetcher_id", sa.UUID(), nullable=True),
        sa.Column("motie_build_id", sa.UUID(), nullable=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("domain", sa.String(512), nullable=False),
        sa.Column(
            "attempt_number",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'draft'"),
            comment=(
                "draft = freshly recorded, not yet promoted; final = the canonical "
                "result for this attempt-group; superseded = a draft eclipsed by a "
                "later iteration; failed = run did not produce usable data."
            ),
        ),
        sa.Column("completeness_score", sa.Float(), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fields_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "field_presence_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("missing_fields_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_fetcher_runs"),
        sa.ForeignKeyConstraint(
            ["parent_run_id"],
            ["data_capture.fetcher_runs.id"],
            name="fk_fetcher_runs_parent_run_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["fetcher_id"],
            ["data_capture.fetchers.id"],
            name="fk_fetcher_runs_fetcher_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ai_fetcher_id"],
            ["data_capture.ai_fetchers.id"],
            name="fk_fetcher_runs_ai_fetcher_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["motie_build_id"],
            ["data_capture.motie_builds.id"],
            name="fk_fetcher_runs_motie_build_id",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "kind IN ('coded', 'ai', 'build_benchmark')",
            name="ck_fetcher_runs_kind",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'final', 'superseded', 'failed')",
            name="ck_fetcher_runs_status",
        ),
        schema="data_capture",
    )
    op.create_index(
        "ix_fetcher_runs_url", "fetcher_runs", ["url"], schema="data_capture"
    )
    op.create_index(
        "ix_fetcher_runs_domain", "fetcher_runs", ["domain"], schema="data_capture"
    )
    op.create_index(
        "ix_fetcher_runs_parent_run_id",
        "fetcher_runs",
        ["parent_run_id"],
        schema="data_capture",
    )
    op.create_index(
        "ix_fetcher_runs_status_started",
        "fetcher_runs",
        ["status", "started_at"],
        schema="data_capture",
    )
    op.create_index(
        "ix_fetcher_runs_motie_build_id",
        "fetcher_runs",
        ["motie_build_id"],
        schema="data_capture",
    )


def downgrade() -> None:
    # fetcher_runs
    op.drop_index(
        "ix_fetcher_runs_motie_build_id",
        table_name="fetcher_runs",
        schema="data_capture",
    )
    op.drop_index(
        "ix_fetcher_runs_status_started",
        table_name="fetcher_runs",
        schema="data_capture",
    )
    op.drop_index(
        "ix_fetcher_runs_parent_run_id",
        table_name="fetcher_runs",
        schema="data_capture",
    )
    op.drop_index(
        "ix_fetcher_runs_domain", table_name="fetcher_runs", schema="data_capture"
    )
    op.drop_index(
        "ix_fetcher_runs_url", table_name="fetcher_runs", schema="data_capture"
    )
    op.drop_table("fetcher_runs", schema="data_capture")

    # motie_builds
    op.drop_index(
        "ix_motie_builds_session_id",
        table_name="motie_builds",
        schema="data_capture",
    )
    op.drop_index(
        "ix_motie_builds_state", table_name="motie_builds", schema="data_capture"
    )
    op.drop_index(
        "ix_motie_builds_project_uuid",
        table_name="motie_builds",
        schema="data_capture",
    )
    op.drop_table("motie_builds", schema="data_capture")

    # fetchers.build_score / build_scored_at
    op.drop_column("fetchers", "build_scored_at", schema="data_capture")
    op.drop_column("fetchers", "build_score", schema="data_capture")

    # ai_fetchers
    op.drop_index(
        "ix_ai_fetchers_enabled_priority",
        table_name="ai_fetchers",
        schema="data_capture",
    )
    op.execute("DROP INDEX IF EXISTS data_capture.uq_ai_fetchers_default_baseline;")
    op.drop_table("ai_fetchers", schema="data_capture")
