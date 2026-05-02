"""Add created_at / updated_at columns to fetcher_runs.

Revision ID: i1a6b4c9d2e3
Revises: h9f5e3a8b1c2
Create Date: 2026-05-02

The Base class in data_capture_service.models.base auto-declares
created_at and updated_at on every model, so SQLAlchemy emits those
columns in the INSERT ... RETURNING clause. The original h9f5e3a8b1c2
migration created fetcher_runs with started_at / finished_at instead
(intentional — semantically distinct from row-insert timestamps), but
forgot to also add the Base-required columns. Result: every INSERT
into data_capture.fetcher_runs raised psycopg.errors.UndefinedColumn
("column fetcher_runs.created_at does not exist").

This mirrors the same fix done for build_flags in f3d9c7a2b8e1.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i1a6b4c9d2e3"
down_revision: Union[str, None] = "h9f5e3a8b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "fetcher_runs",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema="data_capture",
    )
    op.add_column(
        "fetcher_runs",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema="data_capture",
    )


def downgrade() -> None:
    op.drop_column("fetcher_runs", "updated_at", schema="data_capture")
    op.drop_column("fetcher_runs", "created_at", schema="data_capture")
