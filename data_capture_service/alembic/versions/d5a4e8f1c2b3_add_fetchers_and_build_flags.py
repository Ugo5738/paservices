"""Add fetchers registry and build_flags queue.

Revision ID: d5a4e8f1c2b3
Revises: c4e8a1f2d307
Create Date: 2026-04-28

Introduces the V2 registry/queue tables that decouple n8n orchestration
from the data capture service:

- fetchers: registry of all callable scrapers (Motie-built or external proxy).
  References motie_scraper_projects via motie_project_uuid for Motie-built
  fetchers; proxies use api_url_override directly.

- build_flags: queue rows written by parents (e.g. WF A) when a domain has
  no coded fetcher; consumed by WF C to drive Motie build runs.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d5a4e8f1c2b3"
down_revision: Union[str, None] = "c4e8a1f2d307"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- fetchers (registry of callable scrapers) ---
    op.create_table(
        "fetchers",
        sa.Column(
            "id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("domain", sa.String(512), nullable=False),
        # source_type: 'motie' (built via Motie agent) | 'proxy' (forwards to another HTTP service)
        sa.Column("source_type", sa.String(32), nullable=False),
        # FK to motie_scraper_projects.id (UUID) — null for source_type='proxy'
        sa.Column("motie_project_uuid", sa.UUID(), nullable=True),
        sa.Column("route_path", sa.String(512), nullable=False),
        sa.Column(
            "http_method", sa.String(16), nullable=False, server_default=sa.text("'GET'")
        ),
        # param_schema: how the runner injects the property URL into the request, e.g.
        # {"url_param": "listing_url", "url_location": "query"}
        sa.Column(
            "param_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # api_url_override: used for source_type='proxy' (no Motie deployment)
        sa.Column("api_url_override", sa.String(2048), nullable=True),
        sa.Column(
            "is_metered",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
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
        sa.PrimaryKeyConstraint("id", name="pk_fetchers"),
        sa.ForeignKeyConstraint(
            ["motie_project_uuid"],
            ["data_capture.motie_scraper_projects.id"],
            name="fk_fetchers_motie_project_uuid",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "source_type IN ('motie', 'proxy')", name="ck_fetchers_source_type"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')", name="ck_fetchers_status"
        ),
        sa.CheckConstraint(
            "(source_type = 'motie' AND motie_project_uuid IS NOT NULL) "
            "OR (source_type = 'proxy' AND api_url_override IS NOT NULL)",
            name="ck_fetchers_source_consistency",
        ),
        schema="data_capture",
    )

    op.create_index(
        "ix_fetchers_domain", "fetchers", ["domain"], schema="data_capture"
    )
    op.create_index(
        "ix_fetchers_source_type",
        "fetchers",
        ["source_type"],
        schema="data_capture",
    )
    op.create_index(
        "ix_fetchers_status_domain",
        "fetchers",
        ["status", "domain"],
        schema="data_capture",
    )

    # --- build_flags (queue for WF C build trigger) ---
    op.create_table(
        "build_flags",
        sa.Column(
            "id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("domain", sa.String(512), nullable=False),
        sa.Column("reason", sa.String(512), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "attempts", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("picked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_build_flags"),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'done', 'failed')",
            name="ck_build_flags_status",
        ),
        schema="data_capture",
    )

    op.create_index(
        "ix_build_flags_domain", "build_flags", ["domain"], schema="data_capture"
    )
    op.create_index(
        "ix_build_flags_status_created",
        "build_flags",
        ["status", "created_at"],
        schema="data_capture",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_build_flags_status_created",
        table_name="build_flags",
        schema="data_capture",
    )
    op.drop_index(
        "ix_build_flags_domain", table_name="build_flags", schema="data_capture"
    )
    op.drop_table("build_flags", schema="data_capture")

    op.drop_index(
        "ix_fetchers_status_domain", table_name="fetchers", schema="data_capture"
    )
    op.drop_index(
        "ix_fetchers_source_type", table_name="fetchers", schema="data_capture"
    )
    op.drop_index("ix_fetchers_domain", table_name="fetchers", schema="data_capture")
    op.drop_table("fetchers", schema="data_capture")
