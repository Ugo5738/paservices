"""Add motie_scraper_projects table

Revision ID: b3f7a2c91d05
Revises: ac12c7784304
Create Date: 2026-03-17 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3f7a2c91d05"
down_revision: Union[str, None] = "ac12c7784304"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "motie_scraper_projects",
        sa.Column("id", sa.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("domain", sa.String(512), nullable=False),
        sa.Column("motie_project_id", sa.String(256), nullable=False),
        sa.Column("motie_project_name", sa.String(512), nullable=True),
        sa.Column("api_url", sa.String(2048), nullable=True),
        sa.Column("route_path", sa.String(512), nullable=True),
        sa.Column("last_deployment_id", sa.String(256), nullable=True),
        sa.Column("deployment_status", sa.String(64), nullable=True),
        sa.Column("last_session_id", sa.String(256), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.PrimaryKeyConstraint("id", name="pk_motie_scraper_projects"),
        sa.UniqueConstraint("domain", name="uq_motie_scraper_projects_domain"),
        schema="data_capture",
    )

    op.create_index(
        "ix_motie_scraper_projects_domain",
        "motie_scraper_projects",
        ["domain"],
        schema="data_capture",
    )
    op.create_index(
        "ix_motie_scraper_projects_motie_project_id",
        "motie_scraper_projects",
        ["motie_project_id"],
        schema="data_capture",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_motie_scraper_projects_motie_project_id",
        table_name="motie_scraper_projects",
        schema="data_capture",
    )
    op.drop_index(
        "ix_motie_scraper_projects_domain",
        table_name="motie_scraper_projects",
        schema="data_capture",
    )
    op.drop_table("motie_scraper_projects", schema="data_capture")
