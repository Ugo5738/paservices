"""create_role_permissions_table

Revision ID: 81a5f5a67e29
Revises: ae8251f9bc75
Create Date: 2025-05-27 12:15:34.029297

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '81a5f5a67e29'
down_revision: Union[str, None] = 'ae8251f9bc75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
