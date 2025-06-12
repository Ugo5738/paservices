"""create_permissions_table

Revision ID: e8c2ee1b8bed
Revises: 82ddc29a0e99
Create Date: 2025-05-27 12:12:07.728771

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8c2ee1b8bed'
down_revision: Union[str, None] = '82ddc29a0e99'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
