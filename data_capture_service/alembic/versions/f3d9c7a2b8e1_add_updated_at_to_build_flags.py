"""Add updated_at column to build_flags.

Revision ID: f3d9c7a2b8e1
Revises: e7c2b1f9a4d5
Create Date: 2026-04-30

The Base class in data_capture_service.models.base declares both `created_at`
and `updated_at` for every model. The original build_flags migration
(d5a4e8f1c2b3) only added `created_at`, which means the ORM emits SELECT
statements referencing `updated_at` that error out at runtime
(`column build_flags.updated_at does not exist`).

This migration brings the table in line with the model.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3d9c7a2b8e1"
down_revision: Union[str, None] = "e7c2b1f9a4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "build_flags",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema="data_capture",
    )


def downgrade() -> None:
    op.drop_column("build_flags", "updated_at", schema="data_capture")
