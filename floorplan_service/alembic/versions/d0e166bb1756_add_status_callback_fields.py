"""Add status callback fields

Revision ID: d0e166bb1756
Revises: 2e2200ed902f
Create Date: 2025-10-25 02:30:59.555415

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d0e166bb1756"
down_revision: Union[str, None] = "2e2200ed902f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "fp_property_data",
        sa.Column("callback_url", sa.String(length=1024), nullable=True),
        schema="floorplan",
    )
    op.add_column(
        "fp_property_data",
        sa.Column(
            "callback_headers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        schema="floorplan",
    )
    op.add_column(
        "fp_property_data",
        sa.Column("total_floorplans", sa.Integer(), nullable=True),
        schema="floorplan",
    )


def downgrade() -> None:
    op.drop_column("fp_property_data", "total_floorplans", schema="floorplan")
    op.drop_column("fp_property_data", "callback_headers", schema="floorplan")
    op.drop_column("fp_property_data", "callback_url", schema="floorplan")
