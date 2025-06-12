"""create_roles_table

Revision ID: 82ddc29a0e99
Revises: c4054d04812f
Create Date: 2025-05-27 12:11:08.405566

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '82ddc29a0e99'
down_revision: Union[str, None] = 'c4054d04812f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
