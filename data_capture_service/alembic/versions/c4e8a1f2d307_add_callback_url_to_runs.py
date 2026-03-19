"""Add callback_url column to data_capture_runs.

Revision ID: c4e8a1f2d307
Revises: b3f7a2c91d05
Create Date: 2026-03-18
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c4e8a1f2d307"
down_revision = "b3f7a2c91d05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "data_capture_runs",
        sa.Column("callback_url", sa.String(2048), nullable=True),
        schema="data_capture",
    )


def downgrade() -> None:
    op.drop_column("data_capture_runs", "callback_url", schema="data_capture")
