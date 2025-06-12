"""add_email_column_to_profiles_table

Revision ID: e43406c0b240
Revises: 2c258339e8f2
Create Date: 2025-05-29 15:04:52.103273  # Keep your original create date

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e43406c0b240"
down_revision: Union[str, None] = (
    "2c258339e8f2"  # This should be the ID of your latest existing migration
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add the 'email' column to the 'profiles' table
    # It should be a String type and not nullable, matching your model.
    op.add_column("profiles", sa.Column("email", sa.String(), nullable=False))

    # Create an index on the 'email' column, as specified in your model (index=True)
    # unique=False because your model doesn't specify unique=True for email on profiles,
    # and email uniqueness is typically handled by auth.users or a different mechanism.
    # If you intend it to be unique on the profiles table, change unique=True here and in your model.
    op.create_index(op.f("ix_profiles_email"), "profiles", ["email"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the index first
    op.drop_index(op.f("ix_profiles_email"), table_name="profiles")

    # Then drop the column
    op.drop_column("profiles", "email")
